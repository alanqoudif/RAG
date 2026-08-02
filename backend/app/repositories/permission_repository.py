import uuid

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.models.column_permission import ColumnPermission
from app.models.table_permission import TablePermission


def list_effective_table_permissions(
    db: Session, *, tenant_id: uuid.UUID, connection_id: uuid.UUID, user_id: uuid.UUID, role_ids: list[uuid.UUID]
) -> list[TablePermission]:
    """All permission rows that apply to this user: their own user-scoped grants, plus every
    grant attached to a role they hold. Merge semantics (most-permissive union, most-restrictive
    row-filter intersection) live in permission_service, not here.
    """
    conditions = [TablePermission.user_id == user_id]
    if role_ids:
        conditions.append(TablePermission.role_id.in_(role_ids))

    return list(
        db.execute(
            select(TablePermission)
            .where(
                TablePermission.tenant_id == tenant_id,
                TablePermission.connection_id == connection_id,
                or_(*conditions),
            )
            .options(selectinload(TablePermission.column_permissions))
        ).scalars()
    )


def get_by_id(db: Session, tenant_id: uuid.UUID, permission_id: uuid.UUID) -> TablePermission | None:
    return db.execute(
        select(TablePermission).where(
            TablePermission.id == permission_id, TablePermission.tenant_id == tenant_id
        )
    ).scalar_one_or_none()


def create_table_permission(db: Session, permission: TablePermission) -> TablePermission:
    db.add(permission)
    db.commit()
    db.refresh(permission)
    return permission


def create_column_permission(db: Session, permission: ColumnPermission) -> ColumnPermission:
    db.add(permission)
    db.commit()
    db.refresh(permission)
    return permission


def list_by_connection(
    db: Session, tenant_id: uuid.UUID, connection_id: uuid.UUID
) -> list[TablePermission]:
    return list(
        db.execute(
            select(TablePermission)
            .where(TablePermission.tenant_id == tenant_id, TablePermission.connection_id == connection_id)
            .options(selectinload(TablePermission.column_permissions))
        ).scalars()
    )
