import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.tenant import Tenant


def get_by_id(db: Session, tenant_id: uuid.UUID) -> Tenant | None:
    return db.get(Tenant, tenant_id)


def get_by_code(db: Session, code: str) -> Tenant | None:
    return db.execute(select(Tenant).where(Tenant.code == code)).scalar_one_or_none()


def create(db: Session, *, name: str, code: str) -> Tenant:
    tenant = Tenant(name=name, code=code)
    db.add(tenant)
    db.commit()
    db.refresh(tenant)
    return tenant
