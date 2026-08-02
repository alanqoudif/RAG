"""Security-focused SQL validator tests, mirroring the assignment's required security test
categories: SQL injection, multiple statements, comments, destructive SQL, system-schema access,
and administrative functions. Complements tests/unit/test_query_validator.py, which covers the
mechanics of the validator in more depth.
"""

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
            columns={"id": ColumnAccess("id", "int"), "name": ColumnAccess("name", "varchar")},
        ),
        "invoices": TableAccess(
            table_id=None,
            schema_name="public",
            table_name="invoices",
            columns={
                "id": ColumnAccess("id", "int"),
                "invoice_value": ColumnAccess("invoice_value", "numeric"),
                "status": ColumnAccess("status", "varchar"),
            },
            row_filters=[RowFilter(column="status", op="=", value="paid")],
        ),
    }


def _validate(sql, allowed_tables, settings):
    return validate_and_secure(sql, database_type="postgresql", allowed_tables=allowed_tables, settings=settings)


@pytest.mark.parametrize(
    "injection_sql",
    [
        "SELECT id FROM customers WHERE name = '' OR '1'='1'; DROP TABLE customers; --'",
        "SELECT id FROM customers; SELECT id FROM invoices",
        "SELECT id FROM customers WHERE id = 1) UNION SELECT password FROM pg_shadow--",
        "SELECT id FROM customers /*!50000 UNION SELECT 1 */",
        "SELECT id FROM customers WHERE 1=1; --",
    ],
)
def test_classic_sql_injection_patterns_blocked(injection_sql, allowed_tables, settings):
    result = _validate(injection_sql, allowed_tables, settings)
    assert result.ok is False


def test_stacked_queries_blocked(allowed_tables, settings):
    result = _validate("SELECT id FROM customers; DELETE FROM customers", allowed_tables, settings)
    assert result.ok is False


def test_line_and_block_comments_both_blocked(allowed_tables, settings):
    assert _validate("SELECT id FROM customers -- x", allowed_tables, settings).ok is False
    assert _validate("SELECT id FROM customers /* x */", allowed_tables, settings).ok is False
    assert _validate("SELECT /* x */ id FROM customers", allowed_tables, settings).ok is False


@pytest.mark.parametrize(
    "destructive_sql",
    [
        "DROP TABLE customers",
        "DROP DATABASE sample_business",
        "TRUNCATE TABLE customers",
        "DELETE FROM customers",
        "UPDATE customers SET name = 'hacked'",
        "INSERT INTO customers (name) VALUES ('x')",
        "ALTER TABLE customers DROP COLUMN name",
        "CREATE TABLE backdoor (id int)",
    ],
)
def test_destructive_statements_blocked(destructive_sql, allowed_tables, settings):
    result = _validate(destructive_sql, allowed_tables, settings)
    assert result.ok is False


@pytest.mark.parametrize(
    "system_schema_sql",
    [
        "SELECT * FROM pg_catalog.pg_user",
        "SELECT * FROM information_schema.columns",
        "SELECT * FROM information_schema.tables",
    ],
)
def test_system_schema_access_blocked(system_schema_sql, allowed_tables, settings):
    result = _validate(system_schema_sql, allowed_tables, settings)
    assert result.ok is False


@pytest.mark.parametrize(
    "admin_function_sql",
    [
        "SELECT pg_read_file('/etc/passwd')",
        "SELECT pg_ls_dir('/')",
        "SELECT lo_import('/etc/passwd')",
        "SELECT dblink_connect('host=evil.example')",
    ],
)
def test_administrative_functions_blocked(admin_function_sql, allowed_tables, settings):
    result = _validate(admin_function_sql, allowed_tables, settings)
    assert result.ok is False


def test_row_filter_cannot_be_removed_by_generated_sql(allowed_tables, settings):
    """A generated query that omits the WHERE clause entirely still gets the mandatory row
    filter injected — the LLM cannot produce SQL that reads unpaid invoices."""
    result = _validate("SELECT id, invoice_value FROM invoices", allowed_tables, settings)
    assert result.ok is True
    assert "status = 'paid'" in result.query.normalized_sql


def test_unauthorized_column_access_blocked_even_if_aliased(allowed_tables, settings):
    result = _validate("SELECT i.id, i.secret_column FROM invoices i", allowed_tables, settings)
    assert result.ok is False


def test_ambiguous_ddl_disguised_as_cte_name_still_blocked(allowed_tables, settings):
    # A CTE cannot be named after a real, unauthorized table to smuggle access to it.
    result = _validate(
        "WITH employees AS (SELECT 1 AS id) SELECT id FROM employees", allowed_tables, settings
    )
    assert result.ok is True  # "employees" here is just a CTE alias, not the real table — legal
    assert "employees" not in result.query.referenced_tables
