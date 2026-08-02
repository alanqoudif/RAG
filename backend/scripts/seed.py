"""Seed local development data: demo tenant, admin, user, roles, sample database connection,
sample knowledge base + contract document. Safe to run multiple times: every insert is guarded
by an existence check.

Demo credentials (development only, never used outside local Docker):
    tenant_code: acme
    admin:  admin@acme.io / DemoAdmin123!
    user:   analyst@acme.io / DemoUser123!
"""

from pathlib import Path

from app.core.constants import ROLE_ANALYST, ROLE_TENANT_ADMIN
from app.core.security import hash_password
from app.infrastructure.database import SessionLocal
from app.logging_config import get_logger
from app.models.knowledge_base import KnowledgeBase
from app.repositories import (
    database_connection_repository,
    file_repository,
    knowledge_base_repository,
    role_repository,
    tenant_repository,
    user_repository,
)
from app.services.database import connection_service, connection_tester, schema_discovery
from app.services.documents import upload_service
from app.services.documents.document_processor import process_file

logger = get_logger(__name__)

DEMO_TENANT_CODE = "acme"
DEMO_TENANT_NAME = "Acme Corp"
DEMO_ADMIN_EMAIL = "admin@acme.io"
DEMO_ADMIN_PASSWORD = "DemoAdmin123!"
DEMO_USER_EMAIL = "analyst@acme.io"
DEMO_USER_PASSWORD = "DemoUser123!"
DEMO_CONNECTION_NAME = "sample-business"
DEMO_KB_NAME = "contracts"
SAMPLE_CONTRACT_PATH = Path("/app/sample_data/sample_contract.pdf")


def _seed_tenant_and_users(db):
    tenant = tenant_repository.get_by_code(db, DEMO_TENANT_CODE)
    if tenant is None:
        tenant = tenant_repository.create(db, name=DEMO_TENANT_NAME, code=DEMO_TENANT_CODE)
        logger.info("seed_tenant_created", tenant_code=tenant.code)

    roles = role_repository.ensure_default_roles(db, tenant.id)

    admin = user_repository.get_by_email(db, tenant.id, DEMO_ADMIN_EMAIL)
    if admin is None:
        admin = user_repository.create(
            db,
            tenant_id=tenant.id,
            email=DEMO_ADMIN_EMAIL,
            password_hash=hash_password(DEMO_ADMIN_PASSWORD),
            full_name="Demo Tenant Admin",
            is_tenant_admin=True,
        )
        user_repository.assign_role(db, user_id=admin.id, role_id=roles[ROLE_TENANT_ADMIN].id)
        logger.info("seed_admin_created", email=admin.email)

    analyst = user_repository.get_by_email(db, tenant.id, DEMO_USER_EMAIL)
    if analyst is None:
        analyst = user_repository.create(
            db,
            tenant_id=tenant.id,
            email=DEMO_USER_EMAIL,
            password_hash=hash_password(DEMO_USER_PASSWORD),
            full_name="Demo Analyst",
            is_tenant_admin=False,
        )
        user_repository.assign_role(db, user_id=analyst.id, role_id=roles[ROLE_ANALYST].id)
        logger.info("seed_user_created", email=analyst.email)

    return tenant, admin


def _seed_sample_connection(db, tenant, admin):
    connection = database_connection_repository.get_by_name(db, tenant.id, DEMO_CONNECTION_NAME)
    if connection is not None:
        return connection

    connection = connection_service.create_connection(
        db,
        tenant_id=tenant.id,
        created_by=admin.id,
        name=DEMO_CONNECTION_NAME,
        database_type="postgresql",
        host="sample-business-db",
        port=5432,
        database_name="sample_business",
        username="sample_readonly",
        password="sample_readonly_pw",
        ssl_enabled=False,
        connection_options={},
    )
    result = connection_tester.test_connection(db, connection, user_id=admin.id)
    if result.ok:
        schema_discovery.sync_schema(db, connection, user_id=admin.id)
        logger.info("seed_connection_synced", connection=connection.name)
    else:
        logger.warning("seed_connection_test_failed", message=result.message)
    return connection


def _seed_sample_knowledge_base(db, tenant, admin):
    kb = knowledge_base_repository.get_by_name(db, tenant.id, DEMO_KB_NAME)
    if kb is None:
        kb = knowledge_base_repository.create(
            db,
            KnowledgeBase(
                tenant_id=tenant.id,
                created_by=admin.id,
                name=DEMO_KB_NAME,
                description="Sample contracts for document and hybrid chat demos.",
            ),
        )
        logger.info("seed_knowledge_base_created", name=kb.name)

    existing_files = file_repository.list_by_tenant(db, tenant.id, knowledge_base_id=kb.id)
    if existing_files:
        return kb

    if not SAMPLE_CONTRACT_PATH.exists():
        logger.warning("seed_sample_contract_missing", path=str(SAMPLE_CONTRACT_PATH))
        return kb

    data = SAMPLE_CONTRACT_PATH.read_bytes()
    file = upload_service.store_upload(
        db,
        tenant_id=tenant.id,
        uploaded_by=admin.id,
        knowledge_base_id=kb.id,
        original_name="sample_contract.pdf",
        data=data,
        content_type="application/pdf",
    )
    process_file(db, file)
    logger.info("seed_sample_contract_processed", status=file.processing_status)
    return kb


def main() -> None:
    logger.info("seed_started")
    db = SessionLocal()
    try:
        tenant, admin = _seed_tenant_and_users(db)
        _seed_sample_connection(db, tenant, admin)
        _seed_sample_knowledge_base(db, tenant, admin)
        logger.info("seed_completed", tenant_code=tenant.code)
    finally:
        db.close()


if __name__ == "__main__":
    main()
