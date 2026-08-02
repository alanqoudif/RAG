import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.role import Role, UserRole
from app.models.user import User


def get_by_id(db: Session, tenant_id: uuid.UUID, user_id: uuid.UUID) -> User | None:
    """Tenant-scoped lookup: a user ID from another tenant never resolves, by design."""
    return db.execute(
        select(User).where(User.id == user_id, User.tenant_id == tenant_id)
    ).scalar_one_or_none()


def get_by_email(db: Session, tenant_id: uuid.UUID, email: str) -> User | None:
    return db.execute(
        select(User).where(User.tenant_id == tenant_id, User.email == email)
    ).scalar_one_or_none()


def list_by_tenant(db: Session, tenant_id: uuid.UUID) -> list[User]:
    return list(db.execute(select(User).where(User.tenant_id == tenant_id)).scalars())


def create(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    email: str,
    password_hash: str,
    full_name: str | None = None,
    is_tenant_admin: bool = False,
) -> User:
    user = User(
        tenant_id=tenant_id,
        email=email,
        password_hash=password_hash,
        full_name=full_name,
        is_tenant_admin=is_tenant_admin,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_roles(db: Session, tenant_id: uuid.UUID, user_id: uuid.UUID) -> list[Role]:
    rows = db.execute(
        select(Role)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(UserRole.user_id == user_id, Role.tenant_id == tenant_id)
    ).scalars()
    return list(rows)


def assign_role(db: Session, *, user_id: uuid.UUID, role_id: uuid.UUID) -> None:
    existing = db.get(UserRole, {"user_id": user_id, "role_id": role_id})
    if existing is not None:
        return
    db.add(UserRole(user_id=user_id, role_id=role_id))
    db.commit()


def with_roles_loaded(db: Session, tenant_id: uuid.UUID, user_id: uuid.UUID) -> User | None:
    return db.execute(
        select(User)
        .where(User.id == user_id, User.tenant_id == tenant_id)
        .options(selectinload(User.user_roles).selectinload(UserRole.role))
    ).scalar_one_or_none()
