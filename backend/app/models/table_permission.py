import uuid
from typing import TYPE_CHECKING

from sqlalchemy import JSON, Boolean, CheckConstraint, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.column_permission import ColumnPermission


class TablePermission(Base, TimestampMixin):
    """A permission grant scoped to exactly one role OR one user (never both — enforced by the
    check constraint below) for a single table on a single connection.
    """

    __tablename__ = "table_permissions"
    __table_args__ = (
        CheckConstraint(
            "(role_id IS NOT NULL AND user_id IS NULL) OR (role_id IS NULL AND user_id IS NOT NULL)",
            name="chk_permission_subject",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("roles.id", ondelete="CASCADE"), nullable=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )
    connection_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("database_connections.id", ondelete="CASCADE"), nullable=False, index=True
    )
    table_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("database_tables.id", ondelete="CASCADE"), nullable=False, index=True
    )
    can_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    can_insert: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    can_update: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    can_delete: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    row_filter: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    column_permissions: Mapped[list["ColumnPermission"]] = relationship(
        back_populates="table_permission", cascade="all, delete-orphan"
    )
