from app.core.constants import ROLE_TENANT_ADMIN
from app.core.security import hash_password
from app.repositories import role_repository, tenant_repository, user_repository


def _seed_admin_and_login(client, db_session, *, tenant_code="acme"):
    tenant = tenant_repository.create(db_session, name="Acme", code=tenant_code)
    roles = role_repository.ensure_default_roles(db_session, tenant.id)
    user = user_repository.create(
        db_session,
        tenant_id=tenant.id,
        email="admin@acme.io",
        password_hash=hash_password("Sup3rSecret!"),
        is_tenant_admin=True,
    )
    user_repository.assign_role(db_session, user_id=user.id, role_id=roles[ROLE_TENANT_ADMIN].id)
    login = client.post(
        "/api/auth/login",
        json={"tenant_code": tenant_code, "email": "admin@acme.io", "password": "Sup3rSecret!"},
    )
    token = login.json()["access_token"]
    return tenant, user, {"Authorization": f"Bearer {token}"}


def _create_connection_payload(**overrides):
    payload = {
        "name": "sample-db",
        "database_type": "postgresql",
        "host": "localhost",
        "port": 5433,
        "database_name": "sample_business",
        "username": "sample_readonly",
        "password": "sample_readonly_pw",
        "ssl_enabled": False,
        "connection_options": {},
    }
    payload.update(overrides)
    return payload


def test_create_and_get_connection(client, db_session):
    _, _, headers = _seed_admin_and_login(client, db_session)
    response = client.post(
        "/api/database-connections", json=_create_connection_payload(), headers=headers
    )
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "sample-db"
    assert body["status"] == "pending"
    assert "password" not in body
    assert "encrypted_password" not in body

    get_response = client.get(f"/api/database-connections/{body['id']}", headers=headers)
    assert get_response.status_code == 200
    assert get_response.json()["id"] == body["id"]


def test_create_rejects_unsupported_database_type(client, db_session):
    _, _, headers = _seed_admin_and_login(client, db_session)
    response = client.post(
        "/api/database-connections",
        json=_create_connection_payload(database_type="oracle"),
        headers=headers,
    )
    assert response.status_code == 422


def test_create_requires_tenant_admin(client, db_session):
    tenant = tenant_repository.create(db_session, name="Acme", code="acme")
    role_repository.ensure_default_roles(db_session, tenant.id)
    user_repository.create(
        db_session,
        tenant_id=tenant.id,
        email="viewer@acme.io",
        password_hash=hash_password("Sup3rSecret!"),
        is_tenant_admin=False,
    )
    login = client.post(
        "/api/auth/login",
        json={"tenant_code": "acme", "email": "viewer@acme.io", "password": "Sup3rSecret!"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    response = client.post(
        "/api/database-connections", json=_create_connection_payload(), headers=headers
    )
    assert response.status_code == 403


def test_list_and_delete_connection(client, db_session):
    _, _, headers = _seed_admin_and_login(client, db_session)
    create_response = client.post(
        "/api/database-connections", json=_create_connection_payload(), headers=headers
    )
    connection_id = create_response.json()["id"]

    list_response = client.get("/api/database-connections", headers=headers)
    assert len(list_response.json()) == 1

    delete_response = client.delete(f"/api/database-connections/{connection_id}", headers=headers)
    assert delete_response.status_code == 204

    get_response = client.get(f"/api/database-connections/{connection_id}", headers=headers)
    assert get_response.status_code == 404


def test_update_connection_rotates_password(client, db_session):
    _, _, headers = _seed_admin_and_login(client, db_session)
    create_response = client.post(
        "/api/database-connections", json=_create_connection_payload(), headers=headers
    )
    connection_id = create_response.json()["id"]

    update_response = client.put(
        f"/api/database-connections/{connection_id}",
        json={"password": "new-password-value"},
        headers=headers,
    )
    assert update_response.status_code == 200
    assert "password" not in update_response.json()
