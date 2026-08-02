from app.core.constants import ROLE_ANALYST, ROLE_TENANT_ADMIN
from app.core.security import hash_password
from app.models.database_column import DatabaseColumn
from app.models.database_connection import DatabaseConnection
from app.models.database_schema import DatabaseSchema
from app.models.database_table import DatabaseTable
from app.repositories import role_repository, tenant_repository, user_repository


def _seed(db_session):
    tenant = tenant_repository.create(db_session, name="Acme", code="acme")
    roles = role_repository.ensure_default_roles(db_session, tenant.id)
    admin = user_repository.create(
        db_session, tenant_id=tenant.id, email="admin@acme.io", password_hash=hash_password("Sup3rSecret!"), is_tenant_admin=True
    )
    user_repository.assign_role(db_session, user_id=admin.id, role_id=roles[ROLE_TENANT_ADMIN].id)

    connection = DatabaseConnection(tenant_id=tenant.id, name="db", database_type="postgresql", host="h", port=5432)
    db_session.add(connection)
    db_session.flush()
    schema = DatabaseSchema(tenant_id=tenant.id, connection_id=connection.id, schema_name="public")
    db_session.add(schema)
    db_session.flush()
    table = DatabaseTable(tenant_id=tenant.id, connection_id=connection.id, schema_id=schema.id, table_name="customers")
    db_session.add(table)
    db_session.flush()
    column = DatabaseColumn(tenant_id=tenant.id, table_id=table.id, column_name="id", data_type="int")
    db_session.add(column)
    db_session.commit()

    return tenant, admin, roles, connection, table, column


def _login(client, email="admin@acme.io", password="Sup3rSecret!"):
    response = client.post("/api/auth/login", json={"tenant_code": "acme", "email": email, "password": password})
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_admin_sees_full_allowed_schema(client, db_session):
    tenant, admin, roles, connection, table, column = _seed(db_session)
    headers = _login(client)

    response = client.get(f"/api/database-connections/{connection.id}/permissions/allowed-schema", headers=headers)
    assert response.status_code == 200
    assert "customers" in response.json()["allowed_schema"]


def test_create_table_permission_grant(client, db_session):
    tenant, admin, roles, connection, table, column = _seed(db_session)
    headers = _login(client)

    response = client.post(
        f"/api/database-connections/{connection.id}/permissions",
        json={
            "role_id": str(roles[ROLE_ANALYST].id),
            "table_id": str(table.id),
            "can_read": True,
            "row_filter": {"column": "id", "op": ">", "value": 0},
            "column_permissions": [
                {"column_id": str(column.id), "can_read": True, "mask_type": "none"}
            ],
        },
        headers=headers,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["can_read"] is True
    assert len(body["column_permissions"]) == 1


def test_create_permission_requires_exactly_one_subject(client, db_session):
    tenant, admin, roles, connection, table, column = _seed(db_session)
    headers = _login(client)

    response = client.post(
        f"/api/database-connections/{connection.id}/permissions",
        json={
            "role_id": str(roles[ROLE_ANALYST].id),
            "user_id": str(admin.id),
            "table_id": str(table.id),
        },
        headers=headers,
    )
    assert response.status_code == 422


def test_non_admin_cannot_create_permission(client, db_session):
    tenant, admin, roles, connection, table, column = _seed(db_session)
    analyst = user_repository.create(
        db_session, tenant_id=tenant.id, email="analyst@acme.io", password_hash=hash_password("Sup3rSecret!"), is_tenant_admin=False
    )
    user_repository.assign_role(db_session, user_id=analyst.id, role_id=roles[ROLE_ANALYST].id)
    headers = _login(client, email="analyst@acme.io")

    response = client.post(
        f"/api/database-connections/{connection.id}/permissions",
        json={"role_id": str(roles[ROLE_ANALYST].id), "table_id": str(table.id)},
        headers=headers,
    )
    assert response.status_code == 403


def test_analyst_allowed_schema_reflects_grants(client, db_session):
    tenant, admin, roles, connection, table, column = _seed(db_session)
    analyst = user_repository.create(
        db_session, tenant_id=tenant.id, email="analyst@acme.io", password_hash=hash_password("Sup3rSecret!"), is_tenant_admin=False
    )
    user_repository.assign_role(db_session, user_id=analyst.id, role_id=roles[ROLE_ANALYST].id)

    admin_headers = _login(client)
    client.post(
        f"/api/database-connections/{connection.id}/permissions",
        json={"role_id": str(roles[ROLE_ANALYST].id), "table_id": str(table.id), "can_read": True},
        headers=admin_headers,
    )

    analyst_headers = _login(client, email="analyst@acme.io")
    response = client.get(
        f"/api/database-connections/{connection.id}/permissions/allowed-schema", headers=analyst_headers
    )
    assert response.status_code == 200
    assert "customers" in response.json()["allowed_schema"]
