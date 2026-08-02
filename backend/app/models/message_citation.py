import uuid
from typing import TYPE_CHECKING

from sqlalchemy import JSON, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.message import Message


class MessageCitation(Base, TimestampMixin):
    __tablename__ = "message_citations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    message_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("messages.id", ondelete="CASCADE"), nullable=False, index=True
    )
    citation_type: Mapped[str] = mapped_column(String(30), nullable=False)
    file_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("files.id", ondelete="SET NULL"), nullable=True
    )
    chunk_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("document_chunks.id", ondelete="SET NULL"), nullable=True
    )
    query_execution_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("query_executions.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_reference: Mapped[str | None] = mapped_column(Text, nullable=True)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    relevance_score: Mapped[float | None] = mapped_column(Numeric(8, 6), nullable=True)
    citation_metadata: Mapped[dict] = mapped_column("metadata", JSON, nullable=False, default=dict)

    message: Mapped["Message"] = relationship(back_populates="citations")
