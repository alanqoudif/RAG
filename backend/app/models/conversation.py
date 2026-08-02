import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import STATUS_ACTIVE
from app.infrastructure.database import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.message import Message
    from app.models.tenant import Tenant
    from app.models.user import User


class Conversation(Base, TimestampMixin):
    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default=STATUS_ACTIVE)
    active_connection_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    active_knowledge_base_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    settings: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    tenant: Mapped["Tenant"] = relationship()
    user: Mapped["User"] = relationship()
    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan", order_by="Message.created_at"
    )
