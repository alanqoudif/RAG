import uuid
from typing import TYPE_CHECKING

from sqlalchemy import JSON, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.file import File
    from app.models.tenant import Tenant
    from app.models.user import User


class KnowledgeBase(Base, TimestampMixin):
    __tablename__ = "knowledge_bases"
    __table_args__ = (UniqueConstraint("tenant_id", "name", name="uq_knowledge_base_name"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String(255), nullable=True)
    chunking_config: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    tenant: Mapped["Tenant"] = relationship()
    creator: Mapped["User | None"] = relationship()
    files: Mapped[list["File"]] = relationship(back_populates="knowledge_base")
