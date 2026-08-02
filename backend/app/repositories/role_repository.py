import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.constants import DEFAULT_ROLES
from app.models.role import Role


def get_by_id(db: Session, tenant_id: uuid.UUID, role_id: uuid.UUID) -> Role | None:
    return db.execute(
        select(Role).where(Role.id == role_id, Role.tenant_id == tenant_id)
    ).scalar_one_or_none()


def get_by_name(db: Session, tenant_id: uuid.UUID, name: str) -> Role | None:
    return db.execute(
        select(Role).where(Role.tenant_id == tenant_id, Role.name == name)
    ).scalar_one_or_none()


def list_by_tenant(db: Session, tenant_id: uuid.UUID) -> list[Role]:
    return list(db.execute(select(Role).where(Role.tenant_id == tenant_id)).scalars())


def create(db: Session, *, tenant_id: uuid.UUID, name: str, description: str | None = None) -> Role:
    role = Role(tenant_id=tenant_id, name=name, description=description)
    db.add(role)
    db.commit()
    db.refresh(role)
    return role


def ensure_default_roles(db: Session, tenant_id: uuid.UUID) -> dict[str, Role]:
    roles: dict[str, Role] = {}
    for name in DEFAULT_ROLES:
        role = get_by_name(db, tenant_id, name)
        if role is None:
            role = create(db, tenant_id=tenant_id, name=name)
        roles[name] = role
    return roles
