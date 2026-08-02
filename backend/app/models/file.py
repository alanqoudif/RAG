import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, BigInteger, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import STATUS_PENDING
from app.infrastructure.database import Base

if TYPE_CHECKING:
    from app.models.document_chunk import DocumentChunk
    from app.models.knowledge_base import KnowledgeBase
    from app.models.tenant import Tenant
    from app.models.user import User


class File(Base):
    __tablename__ = "files"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    knowledge_base_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("knowledge_bases.id", ondelete="SET NULL"), nullable=True, index=True
    )
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    original_name: Mapped[str] = mapped_column(String(500), nullable=False)
    stored_name: Mapped[str] = mapped_column(String(500), nullable=False)
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    mime_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    extension: Mapped[str | None] = mapped_column(String(30), nullable=True)
    file_size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    checksum: Mapped[str | None] = mapped_column(String(128), nullable=True)
    processing_status: Mapped[str] = mapped_column(String(30), nullable=False, default=STATUS_PENDING, index=True)
    processing_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    extracted_text_length: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    file_metadata: Mapped[dict] = mapped_column("metadata", JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    tenant: Mapped["Tenant"] = relationship()
    uploader: Mapped["User | None"] = relationship()
    knowledge_base: Mapped["KnowledgeBase | None"] = relationship(back_populates="files")
    chunks: Mapped[list["DocumentChunk"]] = relationship(
        back_populates="file", cascade="all, delete-orphan"
    )
