"""End-to-end text-to-SQL pipeline test against the real sample-business-db, with the LLM call
mocked out (so this doesn't depend on Ollama being pulled/running) — everything downstream of
"the model produced this SQL string" is real: permission resolution, SQLGlot validation, row
filter/limit injection, execution, masking, and QueryExecution persistence.
"""

import socket
from unittest.mock import AsyncMock, patch

import pytest

from app.config import get_settings
from app.core.constants import ROLE_TENANT_ADMIN, VALIDATION_PASSED
from app.core.security import hash_password
from app.core.tenant_context import CurrentUser
from app.models.column_permission import ColumnPermission
from app.models.database_column import DatabaseColumn
from app.models.database_schema import DatabaseSchema
from app.models.database_table import DatabaseTable
from app.models.table_permission import TablePermission
from app.repositories import role_repository, tenant_repository, user_repository
from app.services.database import connection_service, text_to_sql_service
from app.services.llm.ollama_client import OllamaClient


def _sample_db_reachable() -> bool:
    try:
        with socket.create_connection(("localhost", 5433), timeout=1):
            return True
    except OSError:
        return False


pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(not _sample_db_reachable(), reason="sample-business-db not reachable"),
]


def _seed_tenant_admin(db_session):
    tenant = tenant_repository.create(db_session, name="Acme", code="acme")
    roles = role_repository.ensure_default_roles(db_session, tenant.id)
    admin = user_repository.create(
        db_session, tenant_id=tenant.id, email="admin@acme.io", password_hash=hash_password("x"), is_tenant_admin=True
    )
    user_repository.assign_role(db_session, user_id=admin.id, role_id=roles[ROLE_TENANT_ADMIN].id)
    return tenant, admin


def _seed_connection(db_session, tenant, admin):
    connection = connection_service.create_connection(
        db_session,
        tenant_id=tenant.id,
        created_by=admin.id,
        name="sample-business",
        database_type="postgresql",
        host="localhost",
        port=5433,
        database_name="sample_business",
        username="sample_readonly",
        password="sample_readonly_pw",
        ssl_enabled=False,
        connection_options={},
    )
    schema = DatabaseSchema(tenant_id=tenant.id, connection_id=connection.id, schema_name="public")
    db_session.add(schema)
    db_session.flush()
    invoices = DatabaseTable(
        tenant_id=tenant.id, connection_id=connection.id, schema_id=schema.id, table_name="invoices"
    )
    db_session.add(invoices)
    db_session.flush()
    columns = [
        DatabaseColumn(tenant_id=tenant.id, table_id=invoices.id, column_name="id", data_type="int"),
        DatabaseColumn(
            tenant_id=tenant.id, table_id=invoices.id, column_name="invoice_value", data_type="numeric"
        ),
        DatabaseColumn(tenant_id=tenant.id, table_id=invoices.id, column_name="status", data_type="varchar"),
        DatabaseColumn(
            tenant_id=tenant.id,
            table_id=invoices.id,
            column_name="billing_contact_ssn",
            data_type="varchar",
            is_sensitive=True,
        ),
    ]
    db_session.add_all(columns)
    db_session.commit()
    return connection, invoices, {c.column_name: c for c in columns}


async def test_full_pipeline_generates_validates_executes_and_persists(db_session):
    tenant, admin = _seed_tenant_admin(db_session)
    connection, invoices, columns = _seed_connection(db_session, tenant, admin)
    current_user = CurrentUser(
        id=admin.id, tenant_id=tenant.id, email=admin.email, is_tenant_admin=True, roles=frozenset()
    )
    ollama_client = OllamaClient(get_settings())

    with patch.object(
        OllamaClient, "generate", new=AsyncMock(return_value="SELECT SUM(invoice_value) AS total FROM invoices WHERE status = 'paid'")
    ):
        outcome = await text_to_sql_service.ask_database(
            db_session,
            connection=connection,
            question="What is the total value of paid invoices?",
            current_user=current_user,
            ollama_client=ollama_client,
        )

    assert outcome.execution_result is not None
    assert outcome.execution_result.ok is True
    assert float(outcome.execution_result.rows[0]["total"]) == 54000.00
    assert outcome.query_execution.validation_status == VALIDATION_PASSED
    assert outcome.query_execution.execution_status == "success"
    assert "invoices" in outcome.query_execution.referenced_tables


async def test_pipeline_rejects_destructive_sql_from_llm(db_session):
    tenant, admin = _seed_tenant_admin(db_session)
    connection, invoices, columns = _seed_connection(db_session, tenant, admin)
    current_user = CurrentUser(
        id=admin.id, tenant_id=tenant.id, email=admin.email, is_tenant_admin=True, roles=frozenset()
    )
    ollama_client = OllamaClient(get_settings())

    with patch.object(OllamaClient, "generate", new=AsyncMock(return_value="DROP TABLE invoices")):
        outcome = await text_to_sql_service.ask_database(
            db_session,
            connection=connection,
            question="drop the invoices table",
            current_user=current_user,
            ollama_client=ollama_client,
        )

    assert outcome.execution_result is None
    assert outcome.query_execution.validation_status == "failed"
    assert outcome.answer_note is not None


async def test_pipeline_masks_sensitive_column_via_permission_grant(db_session):
    tenant, admin = _seed_tenant_admin(db_session)
    connection, invoices, columns = _seed_connection(db_session, tenant, admin)

    from app.core.constants import ROLE_ANALYST

    roles = {r.name: r for r in role_repository.list_by_tenant(db_session, tenant.id)}
    analyst = user_repository.create(
        db_session, tenant_id=tenant.id, email="analyst@acme.io", password_hash=hash_password("x"), is_tenant_admin=False
    )
    user_repository.assign_role(db_session, user_id=analyst.id, role_id=roles[ROLE_ANALYST].id)

    grant = TablePermission(
        tenant_id=tenant.id, role_id=roles[ROLE_ANALYST].id, connection_id=connection.id, table_id=invoices.id, can_read=True
    )
    db_session.add(grant)
    db_session.flush()
    db_session.add(
        ColumnPermission(
            table_permission_id=grant.id, column_id=columns["billing_contact_ssn"].id, can_read=True, mask_type="full"
        )
    )
    db_session.commit()

    current_user = CurrentUser(
        id=analyst.id, tenant_id=tenant.id, email=analyst.email, is_tenant_admin=False, roles=frozenset({"analyst"})
    )
    ollama_client = OllamaClient(get_settings())

    with patch.object(
        OllamaClient, "generate", new=AsyncMock(return_value="SELECT id, billing_contact_ssn FROM invoices")
    ):
        outcome = await text_to_sql_service.ask_database(
            db_session,
            connection=connection,
            question="show ssn",
            current_user=current_user,
            ollama_client=ollama_client,
        )

    assert outcome.execution_result.ok is True
    assert all(row["billing_contact_ssn"] == "***" for row in outcome.execution_result.rows)
