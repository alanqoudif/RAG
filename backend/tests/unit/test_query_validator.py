import pytest

from app.config import get_settings
from app.services.database.permission_service import ColumnAccess, RowFilter, TableAccess
from app.services.database.query_validator import validate_and_secure


@pytest.fixture()
def settings():
    return get_settings()


@pytest.fixture()
def allowed_tables():
    return {
        "customers": TableAccess(
            table_id=None,
            schema_name="public",
            table_name="customers",
            columns={
                "id": ColumnAccess("id", "int"),
                "name": ColumnAccess("name", "varchar"),
                "country": ColumnAccess("country", "varchar"),
            },
        ),
        "invoices": TableAccess(
            table_id=None,
            schema_name="public",
            table_name="invoices",
            columns={
                "id": ColumnAccess("id", "int"),
                "invoice_value": ColumnAccess("invoice_value", "numeric"),
                "status": ColumnAccess("status", "varchar"),
                "order_id": ColumnAccess("order_id", "int"),
            },
            row_filters=[RowFilter(column="status", op="=", value="paid")],
        ),
    }


def _validate(sql, allowed_tables, settings):
    return validate_and_secure(sql, database_type="postgresql", allowed_tables=allowed_tables, settings=settings)


def test_allows_simple_select(allowed_tables, settings):
    result = _validate("SELECT id, name FROM customers", allowed_tables, settings)
    assert result.ok is True
    assert result.query.query_type == "select"
    assert result.query.referenced_tables == ["customers"]


def test_allows_with_cte(allowed_tables, settings):
    sql = "WITH paid AS (SELECT invoice_value FROM invoices WHERE status='paid') SELECT SUM(invoice_value) FROM paid"
    result = _validate(sql, allowed_tables, settings)
    assert result.ok is True
    assert result.query.query_type == "with"


@pytest.mark.parametrize(
    "sql",
    [
        "INSERT INTO customers (name) VALUES ('x')",
        "UPDATE customers SET name = 'x'",
        "DELETE FROM customers",
        "DROP TABLE customers",
        "CREATE TABLE evil (id int)",
        "TRUNCATE TABLE customers",
        "ALTER TABLE customers ADD COLUMN x int",
        "GRANT SELECT ON customers TO public",
        "REVOKE SELECT ON customers FROM public",
        "EXEC sp_who",
        "VACUUM customers",
        "COPY customers TO '/tmp/out.csv'",
    ],
)
def test_blocks_non_select_statements(sql, allowed_tables, settings):
    result = _validate(sql, allowed_tables, settings)
    assert result.ok is False


def test_blocks_multiple_statements(allowed_tables, settings):
    result = _validate("SELECT id FROM customers; DROP TABLE customers;", allowed_tables, settings)
    assert result.ok is False
    assert any("Multiple" in e for e in result.errors)


def test_blocks_sql_comments(allowed_tables, settings):
    result = _validate("SELECT id FROM customers -- sneaky", allowed_tables, settings)
    assert result.ok is False
    assert any("comment" in e.lower() for e in result.errors)

    result2 = _validate("SELECT id FROM customers /* sneaky */", allowed_tables, settings)
    assert result2.ok is False


def test_blocks_select_star(allowed_tables, settings):
    result = _validate("SELECT * FROM customers", allowed_tables, settings)
    assert result.ok is False
    assert any("SELECT *" in e for e in result.errors)


def test_blocks_unauthorized_table(allowed_tables, settings):
    result = _validate("SELECT id FROM employees", allowed_tables, settings)
    assert result.ok is False
    assert any("employees" in e for e in result.errors)


def test_blocks_unauthorized_column(allowed_tables, settings):
    result = _validate("SELECT id, ssn FROM invoices", allowed_tables, settings)
    assert result.ok is False
    assert any("ssn" in e for e in result.errors)


def test_blocks_system_schema_access(allowed_tables, settings):
    result = _validate("SELECT usename FROM pg_catalog.pg_user", allowed_tables, settings)
    assert result.ok is False
    assert any("system schema" in e for e in result.errors)


def test_blocks_information_schema(allowed_tables, settings):
    result = _validate(
        "SELECT table_name FROM information_schema.tables", allowed_tables, settings
    )
    assert result.ok is False


def test_blocks_dangerous_functions(allowed_tables, settings):
    result = _validate("SELECT pg_read_file('/etc/passwd')", allowed_tables, settings)
    assert result.ok is False
    assert any("pg_read_file" in e for e in result.errors)


def test_injects_row_filter_when_absent(allowed_tables, settings):
    result = _validate("SELECT id, invoice_value FROM invoices", allowed_tables, settings)
    assert result.ok is True
    assert "status = 'paid'" in result.query.normalized_sql
    assert "invoices" in result.query.applied_row_filters


def test_row_filter_cannot_be_bypassed_by_or(allowed_tables, settings):
    """Even if the generated SQL tries to weaken the filter with OR, our AND-appended condition
    still narrows the result set — the injected filter is never replaced or OR'd away."""
    result = _validate(
        "SELECT id, invoice_value FROM invoices WHERE status = 'unpaid' OR 1=1", allowed_tables, settings
    )
    assert result.ok is True
    sql = result.query.normalized_sql
    assert "AND" in sql
    assert sql.rstrip().upper().count("WHERE") == 1


def test_row_filter_scoped_only_to_owning_select_in_cte(allowed_tables, settings):
    sql = "WITH paid AS (SELECT invoice_value FROM invoices WHERE status='paid') SELECT SUM(invoice_value) FROM paid"
    result = _validate(sql, allowed_tables, settings)
    assert result.ok is True
    normalized = result.query.normalized_sql
    # the outer SELECT must not reference "invoices" at all (it only selects from the CTE)
    outer_part = normalized.split(")", 1)[1]
    assert "invoices" not in outer_part


def test_injects_row_limit_when_absent(allowed_tables, settings):
    result = _validate("SELECT id, invoice_value FROM invoices", allowed_tables, settings)
    assert result.ok is True
    assert f"LIMIT {settings.sql_max_rows}" in result.query.normalized_sql


def test_clamps_row_limit_when_excessive(allowed_tables, settings):
    result = _validate(
        "SELECT id, invoice_value FROM invoices LIMIT 999999999", allowed_tables, settings
    )
    assert result.ok is True
    assert f"LIMIT {settings.sql_max_rows}" in result.query.normalized_sql
    assert "999999999" not in result.query.normalized_sql


def test_respects_smaller_user_supplied_limit(allowed_tables, settings):
    result = _validate("SELECT id, invoice_value FROM invoices LIMIT 5", allowed_tables, settings)
    assert result.ok is True
    assert "LIMIT 5" in result.query.normalized_sql


def test_blocks_too_many_joins(allowed_tables, settings):
    joins = " ".join(f"JOIN invoices i{n} ON i{n}.id = c.id" for n in range(settings.sql_max_joins + 1))
    sql = f"SELECT c.id FROM customers c {joins}"
    result = _validate(sql, allowed_tables, settings)
    assert result.ok is False
    assert any("joins" in e for e in result.errors)


def test_rejects_empty_sql(allowed_tables, settings):
    result = _validate("", allowed_tables, settings)
    assert result.ok is False


def test_rejects_unparseable_sql(allowed_tables, settings):
    result = _validate("SELECT FROM WHERE ???", allowed_tables, settings)
    assert result.ok is False


def test_subquery_row_filter_scoped_correctly(allowed_tables, settings):
    sql = (
        "SELECT c.id, c.name, "
        "(SELECT SUM(i.invoice_value) FROM invoices i WHERE i.order_id = c.id) AS total "
        "FROM customers c"
    )
    result = _validate(sql, allowed_tables, settings)
    assert result.ok is True
    assert "status = 'paid'" in result.query.normalized_sql
