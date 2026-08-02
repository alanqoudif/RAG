import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.conversation import Conversation


def get_by_id(db: Session, tenant_id: uuid.UUID, conversation_id: uuid.UUID) -> Conversation | None:
    return db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id, Conversation.tenant_id == tenant_id
        )
    ).scalar_one_or_none()


def list_by_user(db: Session, tenant_id: uuid.UUID, user_id: uuid.UUID) -> list[Conversation]:
    return list(
        db.execute(
            select(Conversation)
            .where(Conversation.tenant_id == tenant_id, Conversation.user_id == user_id)
            .order_by(Conversation.created_at.desc())
        ).scalars()
    )


def create(db: Session, conversation: Conversation) -> Conversation:
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


def touch(db: Session, conversation: Conversation, *, at: datetime) -> None:
    conversation.last_message_at = at
    db.add(conversation)
    db.commit()


def delete(db: Session, conversation: Conversation) -> None:
    db.delete(conversation)
    db.commit()
