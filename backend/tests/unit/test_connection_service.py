from app.core.security import hash_password
from app.repositories import tenant_repository, user_repository
from app.services.database import connection_service


def _seed_tenant_and_user(db_session):
    tenant = tenant_repository.create(db_session, name="Acme", code="acme")
    user = user_repository.create(
        db_session,
        tenant_id=tenant.id,
        email="admin@acme.io",
        password_hash=hash_password("x"),
        is_tenant_admin=True,
    )
    return tenant, user


def test_password_is_encrypted_at_rest(db_session):
    tenant, user = _seed_tenant_and_user(db_session)
    connection = connection_service.create_connection(
        db_session,
        tenant_id=tenant.id,
        created_by=user.id,
        name="sample-db",
        database_type="postgresql",
        host="localhost",
        port=5432,
        database_name="sample_business",
        username="sample_readonly",
        password="sample_readonly_pw",
        ssl_enabled=False,
        connection_options={},
    )
    assert connection.encrypted_password is not None
    assert connection.encrypted_password != "sample_readonly_pw"
    assert "sample_readonly_pw" not in connection.encrypted_password


def test_decrypted_details_roundtrip(db_session):
    tenant, user = _seed_tenant_and_user(db_session)
    connection = connection_service.create_connection(
        db_session,
        tenant_id=tenant.id,
        created_by=user.id,
        name="sample-db",
        database_type="postgresql",
        host="localhost",
        port=5432,
        database_name="sample_business",
        username="sample_readonly",
        password="sample_readonly_pw",
        ssl_enabled=False,
        connection_options={},
    )
    details = connection_service.to_connection_details(connection)
    assert details.password == "sample_readonly_pw"
    assert details.host == "localhost"


def test_duplicate_connection_name_rejected(db_session):
    from app.exceptions import ConflictError

    tenant, user = _seed_tenant_and_user(db_session)
    connection_service.create_connection(
        db_session,
        tenant_id=tenant.id,
        created_by=user.id,
        name="dup",
        database_type="postgresql",
        host="h",
        port=5432,
        database_name="d",
        username="u",
        password="p",
        ssl_enabled=False,
        connection_options={},
    )
    try:
        connection_service.create_connection(
            db_session,
            tenant_id=tenant.id,
            created_by=user.id,
            name="dup",
            database_type="postgresql",
            host="h",
            port=5432,
            database_name="d",
            username="u",
            password="p",
            ssl_enabled=False,
            connection_options={},
        )
        raise AssertionError("expected ConflictError")
    except ConflictError:
        pass
