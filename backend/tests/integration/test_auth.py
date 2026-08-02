from app.core.constants import ROLE_TENANT_ADMIN
from app.core.security import hash_password
from app.repositories import role_repository, tenant_repository, user_repository


def _seed_admin(db_session, *, tenant_code="acme", password="Sup3rSecret!"):
    tenant = tenant_repository.create(db_session, name="Acme", code=tenant_code)
    roles = role_repository.ensure_default_roles(db_session, tenant.id)
    user = user_repository.create(
        db_session,
        tenant_id=tenant.id,
        email="admin@acme.io",
        password_hash=hash_password(password),
        full_name="Admin",
        is_tenant_admin=True,
    )
    user_repository.assign_role(db_session, user_id=user.id, role_id=roles[ROLE_TENANT_ADMIN].id)
    return tenant, user


def test_login_success_returns_tokens(client, db_session):
    _seed_admin(db_session)
    response = client.post(
        "/api/auth/login",
        json={"tenant_code": "acme", "email": "admin@acme.io", "password": "Sup3rSecret!"},
    )
    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    assert "refresh_token" in body
    assert body["token_type"] == "bearer"


def test_login_wrong_password_rejected(client, db_session):
    _seed_admin(db_session)
    response = client.post(
        "/api/auth/login",
        json={"tenant_code": "acme", "email": "admin@acme.io", "password": "wrong"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_login_unknown_tenant_rejected(client, db_session):
    _seed_admin(db_session)
    response = client.post(
        "/api/auth/login",
        json={"tenant_code": "does-not-exist", "email": "admin@acme.io", "password": "x"},
    )
    assert response.status_code == 401


def test_me_requires_auth(client):
    response = client.get("/api/auth/me")
    assert response.status_code == 401


def test_me_returns_current_user(client, db_session):
    _seed_admin(db_session)
    login_response = client.post(
        "/api/auth/login",
        json={"tenant_code": "acme", "email": "admin@acme.io", "password": "Sup3rSecret!"},
    )
    access_token = login_response.json()["access_token"]
    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {access_token}"})
    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "admin@acme.io"
    assert body["is_tenant_admin"] is True
    assert ROLE_TENANT_ADMIN in body["roles"]


def test_refresh_rotates_token_and_old_token_is_rejected(client, db_session):
    _seed_admin(db_session)
    login_response = client.post(
        "/api/auth/login",
        json={"tenant_code": "acme", "email": "admin@acme.io", "password": "Sup3rSecret!"},
    )
    old_refresh = login_response.json()["refresh_token"]

    refresh_response = client.post("/api/auth/refresh", json={"refresh_token": old_refresh})
    assert refresh_response.status_code == 200
    new_refresh = refresh_response.json()["refresh_token"]
    assert new_refresh != old_refresh

    reuse_response = client.post("/api/auth/refresh", json={"refresh_token": old_refresh})
    assert reuse_response.status_code == 401


def test_disabled_user_cannot_login(client, db_session):
    _, user = _seed_admin(db_session)
    user.status = "disabled"
    db_session.add(user)
    db_session.commit()

    response = client.post(
        "/api/auth/login",
        json={"tenant_code": "acme", "email": "admin@acme.io", "password": "Sup3rSecret!"},
    )
    assert response.status_code == 401
