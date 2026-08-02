import uuid

from sqlalchemy import delete as sa_delete
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.document_chunk import DocumentChunk


def bulk_create(db: Session, chunks: list[DocumentChunk]) -> list[DocumentChunk]:
    db.add_all(chunks)
    db.commit()
    for chunk in chunks:
        db.refresh(chunk)
    return chunks


def delete_by_file_id(db: Session, tenant_id: uuid.UUID, file_id: uuid.UUID) -> None:
    db.execute(
        sa_delete(DocumentChunk).where(
            DocumentChunk.tenant_id == tenant_id, DocumentChunk.file_id == file_id
        )
    )
    db.commit()


def get_by_ids(db: Session, tenant_id: uuid.UUID, chunk_ids: list[uuid.UUID]) -> list[DocumentChunk]:
    if not chunk_ids:
        return []
    return list(
        db.execute(
            select(DocumentChunk).where(
                DocumentChunk.tenant_id == tenant_id, DocumentChunk.id.in_(chunk_ids)
            )
        ).scalars()
    )
