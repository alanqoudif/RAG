import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.message_citation import MessageCitation


def bulk_create(db: Session, citations: list[MessageCitation]) -> list[MessageCitation]:
    db.add_all(citations)
    db.commit()
    for citation in citations:
        db.refresh(citation)
    return citations


def list_by_message(db: Session, tenant_id: uuid.UUID, message_id: uuid.UUID) -> list[MessageCitation]:
    return list(
        db.execute(
            select(MessageCitation).where(
                MessageCitation.tenant_id == tenant_id, MessageCitation.message_id == message_id
            )
        ).scalars()
    )
