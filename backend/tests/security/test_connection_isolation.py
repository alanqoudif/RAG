from app.core.constants import ROLE_TENANT_ADMIN
from app.core.security import hash_password
from app.repositories import role_repository, tenant_repository, user_repository


def _seed_admin_and_login(client, db_session, *, tenant_code, email):
    tenant = tenant_repository.create(db_session, name=tenant_code.title(), code=tenant_code)
    roles = role_repository.ensure_default_roles(db_session, tenant.id)
    user = user_repository.create(
        db_session,
        tenant_id=tenant.id,
        email=email,
        password_hash=hash_password("Sup3rSecret!"),
        is_tenant_admin=True,
    )
    user_repository.assign_role(db_session, user_id=user.id, role_id=roles[ROLE_TENANT_ADMIN].id)
    login = client.post(
        "/api/auth/login",
        json={"tenant_code": tenant_code, "email": email, "password": "Sup3rSecret!"},
    )
    return tenant, user, {"Authorization": f"Bearer {login.json()['access_token']}"}


def _payload():
    return {
        "name": "shared-name-across-tenants",
        "database_type": "postgresql",
        "host": "localhost",
        "port": 5433,
        "database_name": "sample_business",
        "username": "sample_readonly",
        "password": "sample_readonly_pw",
    }


def test_tenant_a_cannot_read_tenant_b_connection(client, db_session):
    _, _, headers_a = _seed_admin_and_login(client, db_session, tenant_code="tenant-a", email="a@a.io")
    _, _, headers_b = _seed_admin_and_login(client, db_session, tenant_code="tenant-b", email="b@b.io")

    create_response = client.post("/api/database-connections", json=_payload(), headers=headers_b)
    connection_id = create_response.json()["id"]

    response = client.get(f"/api/database-connections/{connection_id}", headers=headers_a)
    assert response.status_code == 404


def test_tenant_a_cannot_delete_tenant_b_connection(client, db_session):
    _, _, headers_a = _seed_admin_and_login(client, db_session, tenant_code="tenant-a", email="a@a.io")
    _, _, headers_b = _seed_admin_and_login(client, db_session, tenant_code="tenant-b", email="b@b.io")

    create_response = client.post("/api/database-connections", json=_payload(), headers=headers_b)
    connection_id = create_response.json()["id"]

    response = client.delete(f"/api/database-connections/{connection_id}", headers=headers_a)
    assert response.status_code == 404

    # still visible to its actual owner
    still_there = client.get(f"/api/database-connections/{connection_id}", headers=headers_b)
    assert still_there.status_code == 200


def test_tenant_a_cannot_test_or_sync_tenant_b_connection(client, db_session):
    _, _, headers_a = _seed_admin_and_login(client, db_session, tenant_code="tenant-a", email="a@a.io")
    _, _, headers_b = _seed_admin_and_login(client, db_session, tenant_code="tenant-b", email="b@b.io")

    create_response = client.post("/api/database-connections", json=_payload(), headers=headers_b)
    connection_id = create_response.json()["id"]

    test_response = client.post(
        f"/api/database-connections/{connection_id}/test", headers=headers_a
    )
    assert test_response.status_code == 404

    sync_response = client.post(
        f"/api/database-connections/{connection_id}/sync-schema", headers=headers_a
    )
    assert sync_response.status_code == 404


def test_connection_names_can_collide_across_tenants(client, db_session):
    """Same connection name in two different tenants must not conflict (uniqueness is per-tenant)."""
    _, _, headers_a = _seed_admin_and_login(client, db_session, tenant_code="tenant-a", email="a@a.io")
    _, _, headers_b = _seed_admin_and_login(client, db_session, tenant_code="tenant-b", email="b@b.io")

    response_a = client.post("/api/database-connections", json=_payload(), headers=headers_a)
    response_b = client.post("/api/database-connections", json=_payload(), headers=headers_b)
    assert response_a.status_code == 201
    assert response_b.status_code == 201
