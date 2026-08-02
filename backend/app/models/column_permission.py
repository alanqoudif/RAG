import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database import Base

if TYPE_CHECKING:
    from app.models.table_permission import TablePermission


class ColumnPermission(Base):
    __tablename__ = "column_permissions"
    __table_args__ = (
        UniqueConstraint("table_permission_id", "column_id", name="uq_column_permission"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    table_permission_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("table_permissions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    column_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("database_columns.id", ondelete="CASCADE"), nullable=False, index=True
    )
    can_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    can_filter: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    can_aggregate: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    mask_type: Mapped[str | None] = mapped_column(String(50), nullable=True)

    table_permission: Mapped["TablePermission"] = relationship(back_populates="column_permissions")
