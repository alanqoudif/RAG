import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import STATUS_PENDING
from app.infrastructure.database import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.database_schema import DatabaseSchema
    from app.models.database_table import DatabaseTable
    from app.models.tenant import Tenant
    from app.models.user import User


class DatabaseConnection(Base, TimestampMixin):
    __tablename__ = "database_connections"
    __table_args__ = (UniqueConstraint("tenant_id", "name", name="uq_database_connection_name"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    database_type: Mapped[str] = mapped_column(String(50), nullable=False)
    host: Mapped[str | None] = mapped_column(String(255), nullable=True)
    port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    database_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    encrypted_password: Mapped[str | None] = mapped_column(Text, nullable=True)
    encrypted_connection_string: Mapped[str | None] = mapped_column(Text, nullable=True)
    ssl_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    ssl_settings: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    connection_options: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default=STATUS_PENDING)
    last_tested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_test_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    schema_sync_status: Mapped[str] = mapped_column(String(30), nullable=False, default=STATUS_PENDING)
    last_schema_sync_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    tenant: Mapped["Tenant"] = relationship()
    creator: Mapped["User | None"] = relationship()
    schemas: Mapped[list["DatabaseSchema"]] = relationship(
        back_populates="connection", cascade="all, delete-orphan"
    )
    tables: Mapped[list["DatabaseTable"]] = relationship(
        back_populates="connection", cascade="all, delete-orphan"
    )
