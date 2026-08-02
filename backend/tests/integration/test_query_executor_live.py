"""Live integration tests against the real `sample-business-db` Postgres container.

These require `docker compose up -d sample-business-db` to be running with the default
credentials from sample_data/sample_business_db.sql (localhost:5433). They are skipped
automatically if that port isn't reachable, so the rest of the suite stays hermetic.
"""

import socket

import pytest

from app.config import get_settings
from app.services.database.adapters.base import ConnectionDetails
from app.services.database.adapters.postgresql import PostgreSQLAdapter
from app.services.database.permission_service import ColumnAccess, TableAccess
from app.services.database.query_executor import execute_query
from app.services.database.query_validator import validate_and_secure


def _sample_db_reachable() -> bool:
    try:
        with socket.create_connection(("localhost", 5433), timeout=1):
            return True
    except OSError:
        return False


pytestmark = pytest.mark.skipif(
    not _sample_db_reachable(),
    reason="sample-business-db is not reachable on localhost:5433 (run `docker compose up -d sample-business-db`)",
)


@pytest.fixture()
def details():
    return ConnectionDetails(
        host="localhost",
        port=5433,
        database_name="sample_business",
        username="sample_readonly",
        password="sample_readonly_pw",
    )


@pytest.fixture()
def allowed_tables():
    return {
        "invoices": TableAccess(
            table_id=None,
            schema_name="public",
            table_name="invoices",
            columns={
                "id": ColumnAccess("id", "int"),
                "invoice_value": ColumnAccess("invoice_value", "numeric"),
                "status": ColumnAccess("status", "varchar"),
                "order_id": ColumnAccess("order_id", "int"),
                "billing_contact_ssn": ColumnAccess("billing_contact_ssn", "varchar", mask_type="full"),
            },
            row_filters=[],
        ),
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
    }


def test_connection_test_succeeds_against_real_db(details):
    adapter = PostgreSQLAdapter()
    result = adapter.test_connection(details)
    assert result.ok is True


def test_schema_discovery_finds_seeded_tables(details):
    adapter = PostgreSQLAdapter()
    schemas = adapter.discover_schemas(details)
    public = next(s for s in schemas if s.name == "public")
    table_names = {t.name for t in public.tables}
    assert {"customers", "products", "orders", "invoices"}.issubset(table_names)


def test_validated_query_executes_and_returns_expected_total(details, allowed_tables):
    settings = get_settings()
    validation = validate_and_secure(
        "SELECT SUM(invoice_value) AS total_paid FROM invoices WHERE status = 'paid'",
        database_type="postgresql",
        allowed_tables=allowed_tables,
        settings=settings,
    )
    assert validation.ok is True

    adapter = PostgreSQLAdapter()
    result = execute_query(
        adapter, details, validation.query.normalized_sql, allowed_tables=allowed_tables, settings=settings
    )
    assert result.ok is True
    assert result.row_count == 1
    # matches the seed data comment in sample_data/sample_business_db.sql
    assert float(result.rows[0]["total_paid"]) == 54000.00


def test_sensitive_column_is_masked_in_execution_result(details, allowed_tables):
    settings = get_settings()
    validation = validate_and_secure(
        "SELECT id, billing_contact_ssn FROM invoices",
        database_type="postgresql",
        allowed_tables=allowed_tables,
        settings=settings,
    )
    assert validation.ok is True

    adapter = PostgreSQLAdapter()
    result = execute_query(
        adapter, details, validation.query.normalized_sql, allowed_tables=allowed_tables, settings=settings
    )
    assert result.ok is True
    assert all(row["billing_contact_ssn"] == "***" for row in result.rows)


def test_write_credentials_are_rejected_read_only_role(details):
    """The sample_readonly role has SELECT-only grants — any write must fail at the database
    level even if it somehow passed validation, as a defense-in-depth check."""
    from sqlalchemy import text
    from sqlalchemy.exc import DBAPIError

    adapter = PostgreSQLAdapter()
    engine = adapter.make_engine(adapter.build_url(details))
    try:
        with engine.connect() as conn, pytest.raises(DBAPIError):
            conn.execute(text("DELETE FROM invoices"))
    finally:
        engine.dispose()
