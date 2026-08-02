import uuid
from typing import TYPE_CHECKING

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.database_table import DatabaseTable


class DatabaseColumn(Base, TimestampMixin):
    __tablename__ = "database_columns"
    __table_args__ = (UniqueConstraint("table_id", "column_name", name="uq_database_column"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    table_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("database_tables.id", ondelete="CASCADE"), nullable=False, index=True
    )
    column_name: Mapped[str] = mapped_column(String(255), nullable=False)
    data_type: Mapped[str] = mapped_column(String(100), nullable=False)
    ordinal_position: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_nullable: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    is_primary_key: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_foreign_key: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_sensitive: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    referenced_schema: Mapped[str | None] = mapped_column(String(255), nullable=True)
    referenced_table: Mapped[str | None] = mapped_column(String(255), nullable=True)
    referenced_column: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    sample_values: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    table: Mapped["DatabaseTable"] = relationship(back_populates="columns")
