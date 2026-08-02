import uuid
from typing import TYPE_CHECKING

from sqlalchemy import JSON, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.database_connection import DatabaseConnection


class QueryExecution(Base, TimestampMixin):
    """Full audit trail of one generated-SQL attempt: what was generated, how it was validated
    and rewritten, and what happened when (if) it ran.
    """

    __tablename__ = "query_executions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    message_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("messages.id", ondelete="SET NULL"), nullable=True, index=True
    )
    connection_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("database_connections.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    question: Mapped[str | None] = mapped_column(Text, nullable=True)
    generated_sql: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_sql: Mapped[str | None] = mapped_column(Text, nullable=True)
    query_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    validation_status: Mapped[str] = mapped_column(String(30), nullable=False)
    validation_errors: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    applied_row_filters: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    referenced_tables: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    referenced_columns: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    execution_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    execution_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    returned_row_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    result_preview: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    connection: Mapped["DatabaseConnection"] = relationship()
