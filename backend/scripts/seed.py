"""Seed local development data: demo tenant, admin, user, roles, sample docs.

Populated incrementally as each domain (connections in Phase 3, knowledge bases/files in
Phase 5, permissions in Phase 4) becomes available. Safe to run multiple times: every insert
is guarded by an existence check.

Demo credentials (development only, never used outside local Docker):
    tenant_code: acme
    admin:  admin@acme.io / DemoAdmin123!
    user:   analyst@acme.io / DemoUser123!
"""

from app.core.constants import ROLE_ANALYST, ROLE_TENANT_ADMIN
from app.core.security import hash_password
from app.infrastructure.database import SessionLocal
from app.logging_config import get_logger
from app.repositories import role_repository, tenant_repository, user_repository

logger = get_logger(__name__)

DEMO_TENANT_CODE = "acme"
DEMO_TENANT_NAME = "Acme Corp"
DEMO_ADMIN_EMAIL = "admin@acme.io"
DEMO_ADMIN_PASSWORD = "DemoAdmin123!"
DEMO_USER_EMAIL = "analyst@acme.io"
DEMO_USER_PASSWORD = "DemoUser123!"


def main() -> None:
    logger.info("seed_started")
    db = SessionLocal()
    try:
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
            user_repository.assign_role(
                db, user_id=admin.id, role_id=roles[ROLE_TENANT_ADMIN].id
            )
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

        logger.info("seed_completed", tenant_code=tenant.code)
    finally:
        db.close()


if __name__ == "__main__":
    main()
