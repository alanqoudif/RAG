import uuid
from typing import TYPE_CHECKING

from sqlalchemy import JSON, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.file import File
    from app.models.knowledge_base import KnowledgeBase


class DocumentChunk(Base, TimestampMixin):
    """Chunk text + metadata live here in the platform DB; the embedding vector itself lives in
    Qdrant (id == this row's id), keeping the vector store as the single source of truth for
    similarity search per the assignment's architecture (Application DB vs. Vector Database as
    separate components) rather than duplicating vectors in both places.
    """

    __tablename__ = "document_chunks"
    __table_args__ = (UniqueConstraint("file_id", "chunk_index", name="uq_document_chunk"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    knowledge_base_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    file_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("files.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    section_title: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    chunk_metadata: Mapped[dict] = mapped_column("metadata", JSON, nullable=False, default=dict)

    file: Mapped["File"] = relationship(back_populates="chunks")
    knowledge_base: Mapped["KnowledgeBase"] = relationship()
