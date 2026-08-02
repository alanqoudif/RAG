import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.database_connection import DatabaseConnection
    from app.models.database_table import DatabaseTable


class DatabaseSchema(Base, TimestampMixin):
    __tablename__ = "database_schemas"
    __table_args__ = (UniqueConstraint("connection_id", "schema_name", name="uq_database_schema"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    connection_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("database_connections.id", ondelete="CASCADE"), nullable=False, index=True
    )
    schema_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    connection: Mapped["DatabaseConnection"] = relationship(back_populates="schemas")
    tables: Mapped[list["DatabaseTable"]] = relationship(
        back_populates="schema", cascade="all, delete-orphan"
    )
