import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.knowledge_base import KnowledgeBase


def get_by_id(db: Session, tenant_id: uuid.UUID, kb_id: uuid.UUID) -> KnowledgeBase | None:
    return db.execute(
        select(KnowledgeBase).where(KnowledgeBase.id == kb_id, KnowledgeBase.tenant_id == tenant_id)
    ).scalar_one_or_none()


def get_by_name(db: Session, tenant_id: uuid.UUID, name: str) -> KnowledgeBase | None:
    return db.execute(
        select(KnowledgeBase).where(KnowledgeBase.tenant_id == tenant_id, KnowledgeBase.name == name)
    ).scalar_one_or_none()


def list_by_tenant(db: Session, tenant_id: uuid.UUID) -> list[KnowledgeBase]:
    return list(
        db.execute(select(KnowledgeBase).where(KnowledgeBase.tenant_id == tenant_id)).scalars()
    )


def create(db: Session, kb: KnowledgeBase) -> KnowledgeBase:
    db.add(kb)
    db.commit()
    db.refresh(kb)
    return kb
