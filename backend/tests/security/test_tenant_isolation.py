from app.core.constants import ROLE_TENANT_ADMIN
from app.core.security import hash_password
from app.repositories import role_repository, tenant_repository, user_repository


def _seed_tenant_with_admin(db_session, *, code, email, password="Sup3rSecret!"):
    tenant = tenant_repository.create(db_session, name=code.title(), code=code)
    roles = role_repository.ensure_default_roles(db_session, tenant.id)
    admin = user_repository.create(
        db_session,
        tenant_id=tenant.id,
        email=email,
        password_hash=hash_password(password),
        full_name="Admin",
        is_tenant_admin=True,
    )
    user_repository.assign_role(db_session, user_id=admin.id, role_id=roles[ROLE_TENANT_ADMIN].id)
    return tenant, admin, roles


def _login(client, tenant_code, email, password="Sup3rSecret!"):
    response = client.post(
        "/api/auth/login",
        json={"tenant_code": tenant_code, "email": email, "password": password},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def test_tenant_a_cannot_see_tenant_b_users(client, db_session):
    _seed_tenant_with_admin(db_session, code="tenant-a", email="admin@a.io")
    _seed_tenant_with_admin(db_session, code="tenant-b", email="admin@b.io")

    token_a = _login(client, "tenant-a", "admin@a.io")
    response = client.get("/api/users", headers={"Authorization": f"Bearer {token_a}"})
    assert response.status_code == 200
    emails = {u["email"] for u in response.json()}
    assert emails == {"admin@a.io"}
    assert "admin@b.io" not in emails


def test_tenant_a_admin_cannot_assign_tenant_b_role_to_tenant_a_user(client, db_session):
    tenant_a, admin_a, roles_a = _seed_tenant_with_admin(db_session, code="tenant-a", email="admin@a.io")
    _, _, roles_b = _seed_tenant_with_admin(db_session, code="tenant-b", email="admin@b.io")

    token_a = _login(client, "tenant-a", "admin@a.io")
    foreign_role_id = str(roles_b[ROLE_TENANT_ADMIN].id)
    response = client.post(
        f"/api/roles/users/{admin_a.id}/assign",
        json={"role_id": foreign_role_id},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert response.status_code == 404


def test_tenant_a_admin_cannot_assign_role_to_tenant_b_user(client, db_session):
    _, _, roles_a = _seed_tenant_with_admin(db_session, code="tenant-a", email="admin@a.io")
    _, admin_b, _ = _seed_tenant_with_admin(db_session, code="tenant-b", email="admin@b.io")

    token_a = _login(client, "tenant-a", "admin@a.io")
    response = client.post(
        f"/api/roles/users/{admin_b.id}/assign",
        json={"role_id": str(roles_a[ROLE_TENANT_ADMIN].id)},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert response.status_code == 404


def test_cross_tenant_jwt_cannot_be_reused_after_tenant_switch(client, db_session):
    """A token's tenant_id claim is trusted, but the user lookup is always tenant-scoped:
    tampering the claim to point at another tenant must not resolve to a real identity."""
    tenant_a, admin_a, _ = _seed_tenant_with_admin(db_session, code="tenant-a", email="admin@a.io")
    tenant_b, _, _ = _seed_tenant_with_admin(db_session, code="tenant-b", email="admin@b.io")

    from app.core.security import AccessTokenClaims, create_access_token

    forged = create_access_token(
        AccessTokenClaims(
            user_id=str(admin_a.id),
            tenant_id=str(tenant_b.id),
            email=admin_a.email,
            is_tenant_admin=True,
            roles=["tenant_admin"],
        )
    )
    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {forged}"})
    assert response.status_code == 401


def test_disabled_user_token_rejected_on_next_request(client, db_session):
    tenant, admin, _ = _seed_tenant_with_admin(db_session, code="tenant-a", email="admin@a.io")
    token = _login(client, "tenant-a", "admin@a.io")

    admin.status = "disabled"
    db_session.add(admin)
    db_session.commit()

    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
