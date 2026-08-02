import uuid
from typing import TYPE_CHECKING

from sqlalchemy import JSON, BigInteger, Boolean, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.database_column import DatabaseColumn
    from app.models.database_connection import DatabaseConnection
    from app.models.database_schema import DatabaseSchema


class DatabaseTable(Base, TimestampMixin):
    __tablename__ = "database_tables"
    __table_args__ = (
        UniqueConstraint("connection_id", "schema_id", "table_name", name="uq_database_table"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    connection_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("database_connections.id", ondelete="CASCADE"), nullable=False, index=True
    )
    schema_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("database_schemas.id", ondelete="CASCADE"), nullable=True
    )
    table_name: Mapped[str] = mapped_column(String(255), nullable=False)
    table_type: Mapped[str] = mapped_column(String(50), nullable=False, default="table")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    estimated_row_count: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    primary_key_columns: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_sensitive: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    table_metadata: Mapped[dict] = mapped_column("metadata", JSON, nullable=False, default=dict)

    connection: Mapped["DatabaseConnection"] = relationship(back_populates="tables")
    schema: Mapped["DatabaseSchema | None"] = relationship(back_populates="tables")
    columns: Mapped[list["DatabaseColumn"]] = relationship(
        back_populates="table", cascade="all, delete-orphan"
    )
