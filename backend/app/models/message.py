import uuid
from typing import TYPE_CHECKING

from sqlalchemy import JSON, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.conversation import Conversation
    from app.models.message_citation import MessageCitation


class Message(Base, TimestampMixin):
    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    parent_message_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("messages.id", ondelete="SET NULL"), nullable=True
    )
    role: Mapped[str] = mapped_column(String(30), nullable=False)
    message_type: Mapped[str] = mapped_column(String(30), nullable=False, default="text")
    content: Mapped[str] = mapped_column(Text, nullable=False)
    structured_content: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    detected_intent: Mapped[str | None] = mapped_column(String(50), nullable=True)
    selected_sources: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    model_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="completed")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")
    citations: Mapped[list["MessageCitation"]] = relationship(
        back_populates="message", cascade="all, delete-orphan"
    )
