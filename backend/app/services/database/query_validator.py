"""SQL security gate for generated queries.

Everything here is enforced by parsing with SQLGlot and walking the AST — never by regex/keyword
matching on the raw string (the one exception is the raw-text comment check, which exists
*in addition to* AST validation because a comment can otherwise smuggle text past a naive
tokenizer in some dialects; SQLGlot itself also strips comments during parsing, so this is
defense in depth, not the primary control).

The LLM's SQL is never trusted: this module independently re-derives which tables/columns are
referenced and re-validates them against the caller-supplied allowlist, then injects mandatory
row/tenant filters and a row limit itself. The LLM cannot see or influence this step.
"""

import re
from dataclasses import dataclass, field

import sqlglot
from sqlglot import exp

from app.config import Settings
from app.core.constants import QUERY_TYPE_SELECT, QUERY_TYPE_WITH
from app.services.database.permission_service import TableAccess

_DIALECT_MAP = {"postgresql": "postgres", "mysql": "mysql", "sqlserver": "tsql"}

_ALWAYS_BLOCKED_SCHEMAS = {
    "pg_catalog",
    "information_schema",
    "pg_toast",
    "mysql",
    "performance_schema",
    "sys",
    "master",
    "msdb",
    "tempdb",
}

_BLOCKED_NODE_TYPES: tuple[type[exp.Expression], ...] = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Drop,
    exp.Create,
    exp.Alter,
    exp.TruncateTable,
    exp.Merge,
    exp.Grant,
    exp.Revoke,
    exp.Command,  # catches EXEC/EXECUTE/CALL/VACUUM/ANALYZE/COPY/ATTACH/DETACH and other admin statements
    exp.Pragma,
)

_BLOCKED_FUNCTION_NAMES = {
    "pg_read_file",
    "pg_read_binary_file",
    "pg_ls_dir",
    "pg_stat_file",
    "lo_import",
    "lo_export",
    "dblink",
    "dblink_connect",
    "copy",
    "xp_cmdshell",
    "sp_executesql",
    "openrowset",
    "opendatasource",
    "load_file",
    "into_outfile",
}

_COMMENT_PATTERN = re.compile(r"--|/\*|\*/|#")


@dataclass
class ValidatedQuery:
    normalized_sql: str
    query_type: str
    referenced_tables: list[str] = field(default_factory=list)
    referenced_columns: list[str] = field(default_factory=list)
    applied_row_filters: dict[str, list[str]] = field(default_factory=dict)


@dataclass
class ValidationResult:
    ok: bool
    errors: list[str] = field(default_factory=list)
    query: ValidatedQuery | None = None


def _sqlglot_dialect(database_type: str) -> str:
    return _DIALECT_MAP.get(database_type, database_type)


def _root_statement_kind(node: exp.Expr) -> str | None:
    # Note: this SQLGlot version has no dedicated EXPLAIN node for every dialect — an EXPLAIN
    # statement it can't model falls back to a generic `Command`, which is already blocked below.
    # EXPLAIN is therefore not currently supported by the validator (fails closed, not open).
    if isinstance(node, exp.Select):
        return QUERY_TYPE_WITH if node.args.get("with_") else QUERY_TYPE_SELECT
    return None


def _table_ref_name(table_node: exp.Table) -> str:
    return table_node.name


def _select_reads_only_ctes(select_node: exp.Select, cte_names: set[str]) -> bool:
    """True if every table this SELECT reads from directly (its own FROM/JOIN, not any nested
    subquery) is a locally-defined CTE — meaning any bare column it projects is CTE output, not
    a direct reference to a real table's column.
    """
    direct_tables: list[str] = []
    from_clause = select_node.args.get("from_")
    if from_clause is not None:
        source = from_clause.this
        if isinstance(source, exp.Table):
            direct_tables.append(source.name)
    for join in select_node.args.get("joins") or []:
        source = join.this
        if isinstance(source, exp.Table):
            direct_tables.append(source.name)
    return bool(direct_tables) and all(t in cte_names for t in direct_tables)


def _find_blocked_nodes(tree: exp.Expr) -> list[str]:
    found = []
    for node in tree.walk():
        if isinstance(node, _BLOCKED_NODE_TYPES):
            found.append(type(node).__name__)
        if isinstance(node, (exp.Anonymous, exp.Func)):
            name = (node.name or "").lower()
            if name in _BLOCKED_FUNCTION_NAMES:
                found.append(f"function:{name}")
    return found


def _resolve_row_filter_condition(row_filter, table_alias: str) -> exp.Expression:
    column = exp.column(row_filter.column, table=table_alias)
    value = exp.convert(row_filter.value)
    op = row_filter.op
    if op == "=":
        return exp.EQ(this=column, expression=value)
    if op == "!=":
        return exp.NEQ(this=column, expression=value)
    if op == "<":
        return exp.LT(this=column, expression=value)
    if op == "<=":
        return exp.LTE(this=column, expression=value)
    if op == ">":
        return exp.GT(this=column, expression=value)
    if op == ">=":
        return exp.GTE(this=column, expression=value)
    if op == "in":
        values = row_filter.value if isinstance(row_filter.value, list) else [row_filter.value]
        return exp.In(this=column, expressions=[exp.convert(v) for v in values])
    raise ValueError(f"Unsupported row filter operator: {op}")


def validate_and_secure(
    raw_sql: str,
    *,
    database_type: str,
    allowed_tables: dict[str, TableAccess],
    settings: Settings,
) -> ValidationResult:
    errors: list[str] = []

    if not raw_sql or not raw_sql.strip():
        return ValidationResult(ok=False, errors=["Empty SQL."])

    if _COMMENT_PATTERN.search(raw_sql):
        return ValidationResult(ok=False, errors=["SQL comments are not permitted."])

    # Reject multiple statements at the text level too: a trailing ';' followed by more content,
    # or more than one non-empty ';'-delimited segment.
    segments = [s for s in raw_sql.strip().rstrip(";").split(";") if s.strip()]
    if len(segments) > 1:
        return ValidationResult(ok=False, errors=["Multiple SQL statements are not permitted."])

    dialect = _sqlglot_dialect(database_type)
    try:
        statements = sqlglot.parse(raw_sql, dialect=dialect)
    except Exception as exc:  # noqa: BLE001 -- any parse failure is a validation failure
        return ValidationResult(ok=False, errors=[f"SQL could not be parsed: {type(exc).__name__}"])

    statements = [s for s in statements if s is not None]
    if len(statements) != 1:
        return ValidationResult(ok=False, errors=["Exactly one SQL statement is required."])

    tree = statements[0]
    assert tree is not None  # guaranteed by the filter above; narrows Expr | None for mypy
    query_type = _root_statement_kind(tree)
    if query_type is None:
        return ValidationResult(
            ok=False, errors=[f"Statement type '{type(tree).__name__}' is not permitted; only SELECT/WITH/EXPLAIN are allowed."]
        )

    blocked = _find_blocked_nodes(tree)
    if blocked:
        errors.append(f"Blocked constructs found: {sorted(set(blocked))}")

    if list(tree.find_all(exp.Star)):
        errors.append("SELECT * is not permitted; select explicit allowed columns.")

    with_clause = tree.args.get("with_")
    cte_names = {cte.alias for cte in with_clause.expressions} if with_clause else set()

    referenced_tables: set[str] = set()
    for table_node in tree.find_all(exp.Table):
        table_name = _table_ref_name(table_node)
        if table_name in cte_names:
            continue  # a reference to a locally-defined CTE, not a real table
        schema_part = (table_node.db or "").lower()
        if schema_part in _ALWAYS_BLOCKED_SCHEMAS:
            errors.append(f"Access to system schema '{schema_part}' is not permitted.")
            continue
        if table_name not in allowed_tables:
            errors.append(f"Table '{table_name}' is not in the permitted schema for this user.")
            continue
        referenced_tables.add(table_name)

    referenced_columns: set[str] = set()
    for column_node in tree.find_all(exp.Column):
        col_name = column_node.name
        table_hint = column_node.table
        if table_hint and table_hint in allowed_tables:
            allowed_cols = allowed_tables[table_hint].columns
            if col_name not in allowed_cols:
                errors.append(f"Column '{table_hint}.{col_name}' is not permitted.")
            else:
                referenced_columns.add(f"{table_hint}.{col_name}")
        elif table_hint:
            # Qualified by an alias, not a bare table name — checked via alias resolution below.
            referenced_columns.add(f"{table_hint}.{col_name}")
        else:
            owning_select = column_node.find_ancestor(exp.Select)
            scope_is_cte_only = owning_select is not None and _select_reads_only_ctes(owning_select, cte_names)
            if scope_is_cte_only:
                # This column comes from a CTE's own output, not directly from a real table —
                # it was already validated when the CTE body itself was checked.
                pass
            elif not any(col_name in t.columns for t in allowed_tables.values() if t.table_name in referenced_tables):
                errors.append(f"Column '{col_name}' is not permitted or is ambiguous.")
            else:
                referenced_columns.add(col_name)

    # Resolve aliases back to real table names to validate column access properly.
    alias_to_table: dict[str, str] = {}
    for table_node in tree.find_all(exp.Table):
        alias_to_table[table_node.alias_or_name] = table_node.name
    for column_node in tree.find_all(exp.Column):
        table_hint = column_node.table
        if table_hint and table_hint not in allowed_tables and table_hint in alias_to_table:
            real_table = alias_to_table[table_hint]
            if real_table in allowed_tables and column_node.name not in allowed_tables[real_table].columns:
                errors.append(f"Column '{table_hint}.{column_node.name}' is not permitted.")

    if len(list(tree.find_all(exp.Join))) > settings.sql_max_joins:
        errors.append(f"Query exceeds the maximum allowed joins ({settings.sql_max_joins}).")

    if isinstance(tree, exp.Select):
        projection_count = len(tree.selects)
        if projection_count > settings.sql_max_columns:
            errors.append(f"Query exceeds the maximum allowed selected columns ({settings.sql_max_columns}).")

    if errors:
        return ValidationResult(ok=False, errors=errors)

    # Attach each filter to the specific SELECT that owns that table reference (found via the
    # AST's own ancestor chain) — never to every SELECT in the tree. Otherwise a filter on a table
    # used only inside a CTE body would leak into an outer SELECT that never references it,
    # producing an out-of-scope column reference and broken SQL.
    applied_filters: dict[str, list[str]] = {}
    for table_node in tree.find_all(exp.Table):
        table_name = table_node.name
        if table_name in cte_names:
            continue
        access = allowed_tables.get(table_name)
        if access is None or not access.row_filters:
            continue
        owning_select = table_node.find_ancestor(exp.Select)
        if owning_select is None:
            continue
        alias = table_node.alias_or_name
        for row_filter in access.row_filters:
            condition = _resolve_row_filter_condition(row_filter, alias)
            owning_select.where(condition, append=True, copy=False)
            applied_filters.setdefault(table_name, []).append(
                f"{row_filter.column} {row_filter.op} {row_filter.value!r}"
            )

    if isinstance(tree, exp.Select):
        existing_limit = tree.args.get("limit")
        if existing_limit is None:
            tree.set("limit", exp.Limit(expression=exp.convert(settings.sql_max_rows)))
        else:
            try:
                current_limit_value = int(existing_limit.expression.this)
                if current_limit_value > settings.sql_max_rows:
                    tree.set("limit", exp.Limit(expression=exp.convert(settings.sql_max_rows)))
            except (TypeError, ValueError, AttributeError):
                tree.set("limit", exp.Limit(expression=exp.convert(settings.sql_max_rows)))

    try:
        normalized_sql = tree.sql(dialect=dialect)
    except Exception as exc:  # noqa: BLE001
        return ValidationResult(ok=False, errors=[f"Failed to render normalized SQL: {type(exc).__name__}"])

    # Re-parse the rewritten SQL as a final sanity check: it must still be a single, valid statement.
    try:
        reparsed = sqlglot.parse(normalized_sql, dialect=dialect)
        if len([s for s in reparsed if s is not None]) != 1:
            return ValidationResult(ok=False, errors=["Rewritten SQL failed re-validation."])
    except Exception as exc:  # noqa: BLE001
        return ValidationResult(ok=False, errors=[f"Rewritten SQL failed re-validation: {type(exc).__name__}"])

    return ValidationResult(
        ok=True,
        query=ValidatedQuery(
            normalized_sql=normalized_sql,
            query_type=query_type,
            referenced_tables=sorted(referenced_tables),
            referenced_columns=sorted(referenced_columns),
            applied_row_filters=applied_filters,
        ),
    )
