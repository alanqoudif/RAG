from app.core.constants import ROLE_ANALYST
from app.core.security import hash_password
from app.core.tenant_context import CurrentUser
from app.models.column_permission import ColumnPermission
from app.models.database_column import DatabaseColumn
from app.models.database_connection import DatabaseConnection
from app.models.database_schema import DatabaseSchema
from app.models.database_table import DatabaseTable
from app.models.table_permission import TablePermission
from app.repositories import role_repository, tenant_repository, user_repository
from app.services.database import permission_service


def _seed_connection_with_tables(db_session, tenant):
    connection = DatabaseConnection(
        tenant_id=tenant.id, name="db", database_type="postgresql", host="h", port=5432
    )
    db_session.add(connection)
    db_session.flush()

    schema = DatabaseSchema(tenant_id=tenant.id, connection_id=connection.id, schema_name="public")
    db_session.add(schema)
    db_session.flush()

    customers = DatabaseTable(
        tenant_id=tenant.id, connection_id=connection.id, schema_id=schema.id, table_name="customers"
    )
    invoices = DatabaseTable(
        tenant_id=tenant.id, connection_id=connection.id, schema_id=schema.id, table_name="invoices"
    )
    db_session.add_all([customers, invoices])
    db_session.flush()

    cols = [
        DatabaseColumn(tenant_id=tenant.id, table_id=customers.id, column_name="id", data_type="int"),
        DatabaseColumn(tenant_id=tenant.id, table_id=customers.id, column_name="name", data_type="varchar"),
        DatabaseColumn(tenant_id=tenant.id, table_id=invoices.id, column_name="id", data_type="int"),
        DatabaseColumn(
            tenant_id=tenant.id, table_id=invoices.id, column_name="invoice_value", data_type="numeric"
        ),
        DatabaseColumn(
            tenant_id=tenant.id,
            table_id=invoices.id,
            column_name="billing_contact_ssn",
            data_type="varchar",
            is_sensitive=True,
        ),
    ]
    db_session.add_all(cols)
    db_session.commit()
    return connection, customers, invoices


def _make_current_user(user, roles):
    return CurrentUser(
        id=user.id,
        tenant_id=user.tenant_id,
        email=user.email,
        is_tenant_admin=user.is_tenant_admin,
        roles=frozenset(roles),
    )


def test_tenant_admin_sees_all_tables_and_columns(db_session):
    tenant = tenant_repository.create(db_session, name="Acme", code="acme")
    admin = user_repository.create(
        db_session, tenant_id=tenant.id, email="admin@acme.io", password_hash=hash_password("x"), is_tenant_admin=True
    )
    connection, customers, invoices = _seed_connection_with_tables(db_session, tenant)

    current_user = _make_current_user(admin, [])
    allowed = permission_service.resolve_allowed_tables(db_session, connection_id=connection.id, current_user=current_user)

    assert set(allowed.keys()) == {"customers", "invoices"}
    assert "billing_contact_ssn" in allowed["invoices"].columns


def test_non_admin_sees_nothing_without_grants(db_session):
    tenant = tenant_repository.create(db_session, name="Acme", code="acme")
    role_repository.ensure_default_roles(db_session, tenant.id)
    viewer = user_repository.create(
        db_session, tenant_id=tenant.id, email="viewer@acme.io", password_hash=hash_password("x"), is_tenant_admin=False
    )
    connection, customers, invoices = _seed_connection_with_tables(db_session, tenant)

    current_user = _make_current_user(viewer, [ROLE_ANALYST])
    allowed = permission_service.resolve_allowed_tables(db_session, connection_id=connection.id, current_user=current_user)

    assert allowed == {}


def test_role_grant_gives_table_access_with_all_columns_by_default(db_session):
    tenant = tenant_repository.create(db_session, name="Acme", code="acme")
    roles = role_repository.ensure_default_roles(db_session, tenant.id)
    analyst = user_repository.create(
        db_session, tenant_id=tenant.id, email="analyst@acme.io", password_hash=hash_password("x"), is_tenant_admin=False
    )
    connection, customers, invoices = _seed_connection_with_tables(db_session, tenant)

    grant = TablePermission(
        tenant_id=tenant.id,
        role_id=roles[ROLE_ANALYST].id,
        connection_id=connection.id,
        table_id=customers.id,
        can_read=True,
    )
    db_session.add(grant)
    db_session.commit()

    current_user = _make_current_user(analyst, [ROLE_ANALYST])
    allowed = permission_service.resolve_allowed_tables(db_session, connection_id=connection.id, current_user=current_user)

    assert set(allowed.keys()) == {"customers"}
    assert set(allowed["customers"].columns.keys()) == {"id", "name"}


def test_column_permission_restricts_sensitive_column(db_session):
    tenant = tenant_repository.create(db_session, name="Acme", code="acme")
    roles = role_repository.ensure_default_roles(db_session, tenant.id)
    analyst = user_repository.create(
        db_session, tenant_id=tenant.id, email="analyst@acme.io", password_hash=hash_password("x"), is_tenant_admin=False
    )
    connection, customers, invoices = _seed_connection_with_tables(db_session, tenant)

    ssn_column = next(c for c in invoices.columns if c.column_name == "billing_contact_ssn")
    grant = TablePermission(
        tenant_id=tenant.id,
        role_id=roles[ROLE_ANALYST].id,
        connection_id=connection.id,
        table_id=invoices.id,
        can_read=True,
    )
    db_session.add(grant)
    db_session.flush()
    db_session.add(
        ColumnPermission(table_permission_id=grant.id, column_id=ssn_column.id, can_read=False)
    )
    db_session.commit()

    current_user = _make_current_user(analyst, [ROLE_ANALYST])
    allowed = permission_service.resolve_allowed_tables(db_session, connection_id=connection.id, current_user=current_user)

    assert "billing_contact_ssn" not in allowed["invoices"].columns
    assert "invoice_value" in allowed["invoices"].columns


def test_row_filter_included_in_table_access(db_session):
    tenant = tenant_repository.create(db_session, name="Acme", code="acme")
    roles = role_repository.ensure_default_roles(db_session, tenant.id)
    analyst = user_repository.create(
        db_session, tenant_id=tenant.id, email="analyst@acme.io", password_hash=hash_password("x"), is_tenant_admin=False
    )
    connection, customers, invoices = _seed_connection_with_tables(db_session, tenant)

    grant = TablePermission(
        tenant_id=tenant.id,
        role_id=roles[ROLE_ANALYST].id,
        connection_id=connection.id,
        table_id=invoices.id,
        can_read=True,
        row_filter={"column": "status", "op": "=", "value": "paid"},
    )
    db_session.add(grant)
    db_session.commit()

    current_user = _make_current_user(analyst, [ROLE_ANALYST])
    allowed = permission_service.resolve_allowed_tables(db_session, connection_id=connection.id, current_user=current_user)

    assert len(allowed["invoices"].row_filters) == 1
    assert allowed["invoices"].row_filters[0].column == "status"


def test_to_prompt_schema_shape_matches_pdf_example(db_session):
    tenant = tenant_repository.create(db_session, name="Acme", code="acme")
    admin = user_repository.create(
        db_session, tenant_id=tenant.id, email="admin@acme.io", password_hash=hash_password("x"), is_tenant_admin=True
    )
    connection, customers, invoices = _seed_connection_with_tables(db_session, tenant)
    current_user = _make_current_user(admin, [])
    allowed = permission_service.resolve_allowed_tables(db_session, connection_id=connection.id, current_user=current_user)
    prompt_schema = permission_service.to_prompt_schema(allowed)

    assert "customers" in prompt_schema
    assert "access" in prompt_schema["customers"]
    assert "columns" in prompt_schema["customers"]
    assert isinstance(prompt_schema["customers"]["columns"], list)
