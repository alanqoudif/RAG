import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.message import Message


def get_by_id(db: Session, tenant_id: uuid.UUID, message_id: uuid.UUID) -> Message | None:
    return db.execute(
        select(Message).where(Message.id == message_id, Message.tenant_id == tenant_id)
    ).scalar_one_or_none()


def list_by_conversation(db: Session, tenant_id: uuid.UUID, conversation_id: uuid.UUID) -> list[Message]:
    return list(
        db.execute(
            select(Message)
            .where(Message.tenant_id == tenant_id, Message.conversation_id == conversation_id)
            .order_by(Message.created_at)
        ).scalars()
    )


def create(db: Session, message: Message) -> Message:
    db.add(message)
    db.commit()
    db.refresh(message)
    return message
