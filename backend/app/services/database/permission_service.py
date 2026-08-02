"""Resolves what a specific user may see and do against a specific connection.

This is the single place that turns "roles + table_permissions + column_permissions" into a
concrete, per-request allowlist. Both the SQL prompt builder (what the LLM is told exists) and
the SQL validator (what is allowed to actually run) call into this module — never duplicate the
merge logic elsewhere. Tenant admins bypass table/column/row restrictions entirely (they own the
tenant's security configuration) but are still subject to the same read-only SQL controls as
everyone else.
"""

import uuid
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.core.constants import ACCESS_READ, ACCESS_READ_WRITE
from app.core.tenant_context import CurrentUser
from app.models.database_table import DatabaseTable
from app.repositories import database_schema_repository, permission_repository, role_repository


@dataclass
class ColumnAccess:
    name: str
    data_type: str
    can_read: bool = True
    can_filter: bool = True
    can_aggregate: bool = True
    mask_type: str | None = None
    is_sensitive: bool = False


@dataclass
class RowFilter:
    column: str
    op: str
    value: object


@dataclass
class TableAccess:
    table_id: uuid.UUID
    schema_name: str
    table_name: str
    access: str = ACCESS_READ
    columns: dict[str, ColumnAccess] = field(default_factory=dict)
    row_filters: list[RowFilter] = field(default_factory=list)


def _parse_row_filter(raw: dict) -> RowFilter | None:
    if not raw or "column" not in raw or "op" not in raw:
        return None
    return RowFilter(column=raw["column"], op=raw["op"], value=raw.get("value"))


def resolve_allowed_tables(
    db: Session, *, connection_id: uuid.UUID, current_user: CurrentUser
) -> dict[str, TableAccess]:
    """Returns tables keyed by table_name (unique per connection in the schemas we support)."""
    cached_tables = database_schema_repository.list_tables(
        db, current_user.tenant_id, connection_id
    )
    tables_by_id = {t.id: t for t in cached_tables}

    if current_user.is_tenant_admin:
        return {
            t.table_name: TableAccess(
                table_id=t.id,
                schema_name=t.schema.schema_name if t.schema else "",
                table_name=t.table_name,
                access=ACCESS_READ,
                columns={
                    c.column_name: ColumnAccess(
                        name=c.column_name,
                        data_type=c.data_type,
                        is_sensitive=c.is_sensitive,
                    )
                    for c in t.columns
                },
                row_filters=[],
            )
            for t in cached_tables
        }

    role_ids = [r.id for r in role_repository.list_by_tenant(db, current_user.tenant_id) if r.name in current_user.roles]
    grants = permission_repository.list_effective_table_permissions(
        db,
        tenant_id=current_user.tenant_id,
        connection_id=connection_id,
        user_id=current_user.id,
        role_ids=role_ids,
    )

    result: dict[str, TableAccess] = {}
    for grant in grants:
        if not grant.can_read:
            continue
        table: DatabaseTable | None = tables_by_id.get(grant.table_id)
        if table is None:
            continue

        access = TableAccess(
            table_id=table.id,
            schema_name=table.schema.schema_name if table.schema else "",
            table_name=table.table_name,
            access=ACCESS_READ_WRITE if (grant.can_insert or grant.can_update or grant.can_delete) else ACCESS_READ,
        )
        if table.table_name in result:
            access = result[table.table_name]
        else:
            access.columns = {
                c.column_name: ColumnAccess(name=c.column_name, data_type=c.data_type, is_sensitive=c.is_sensitive)
                for c in table.columns
            }

        explicit_columns = {cp.column_id: cp for cp in grant.column_permissions}
        if explicit_columns:
            column_by_id = {c.id: c for c in table.columns}
            for column_id, col_perm in explicit_columns.items():
                column = column_by_id.get(column_id)
                if column is None:
                    continue
                if not col_perm.can_read:
                    access.columns.pop(column.column_name, None)
                    continue
                access.columns[column.column_name] = ColumnAccess(
                    name=column.column_name,
                    data_type=column.data_type,
                    can_read=col_perm.can_read,
                    can_filter=col_perm.can_filter,
                    can_aggregate=col_perm.can_aggregate,
                    mask_type=col_perm.mask_type,
                    is_sensitive=column.is_sensitive,
                )

        row_filter = _parse_row_filter(grant.row_filter)
        if row_filter is not None and row_filter not in access.row_filters:
            access.row_filters.append(row_filter)

        result[table.table_name] = access

    return result


def to_prompt_schema(allowed_tables: dict[str, TableAccess]) -> dict:
    """The exact shape the assignment's PDF shows for `allowed_schema` — this, and only this,
    is what the LLM prompt includes. Sensitive/unauthorized columns are already excluded.
    """
    return {
        table_name: {
            "access": access.access,
            "columns": sorted(access.columns.keys()),
        }
        for table_name, access in allowed_tables.items()
        if access.columns  # a table with zero readable columns is not useful to expose
    }
