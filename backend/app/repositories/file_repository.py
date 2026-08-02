import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.file import File


def get_by_id(db: Session, tenant_id: uuid.UUID, file_id: uuid.UUID) -> File | None:
    return db.execute(
        select(File).where(File.id == file_id, File.tenant_id == tenant_id)
    ).scalar_one_or_none()


def list_by_tenant(
    db: Session, tenant_id: uuid.UUID, *, knowledge_base_id: uuid.UUID | None = None
) -> list[File]:
    query = select(File).where(File.tenant_id == tenant_id)
    if knowledge_base_id is not None:
        query = query.where(File.knowledge_base_id == knowledge_base_id)
    return list(db.execute(query.order_by(File.created_at.desc())).scalars())


def create(db: Session, file: File) -> File:
    db.add(file)
    db.commit()
    db.refresh(file)
    return file


def update_status(
    db: Session,
    file: File,
    *,
    status: str,
    error: str | None = None,
    page_count: int | None = None,
    extracted_text_length: int | None = None,
    processed_at: datetime | None = None,
) -> File:
    file.processing_status = status
    file.processing_error = error
    if page_count is not None:
        file.page_count = page_count
    if extracted_text_length is not None:
        file.extracted_text_length = extracted_text_length
    if processed_at is not None:
        file.processed_at = processed_at
    db.add(file)
    db.commit()
    db.refresh(file)
    return file


def delete(db: Session, file: File) -> None:
    db.delete(file)
    db.commit()
