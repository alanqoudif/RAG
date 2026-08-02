"""Parse -> chunk -> embed -> index -> save metadata -> mark file completed/failed.

This is the function both the Celery task and (in tests) direct callers invoke — the task
wrapper (app.workers.tasks.process_file) is a thin shell around this.
"""

import hashlib
import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.constants import (
    AUDIT_FILE_PROCESSED,
    AUDIT_FILE_PROCESSING_FAILED,
    STATUS_COMPLETED,
    STATUS_FAILED,
    STATUS_PROCESSING,
)
from app.models.document_chunk import DocumentChunk
from app.models.file import File
from app.repositories import document_chunk_repository, file_repository
from app.services.audit_service import record_audit_event
from app.services.documents.chunking_service import chunk_segments
from app.services.documents.embedding_service import get_embedding_provider
from app.services.documents.parsers.dispatch import parse_document
from app.storage.minio_client import get_object_storage
from app.vector_store.qdrant_store import ChunkPoint, get_vector_store


def process_file(db: Session, file: File) -> None:
    file_repository.update_status(db, file, status=STATUS_PROCESSING)

    try:
        storage = get_object_storage()
        data = storage.get_object_bytes(file.storage_path)

        settings = get_settings()
        segments, page_count = parse_document(file.extension or "", data)
        chunks = chunk_segments(
            segments,
            chunk_size_tokens=settings.chunk_size_tokens,
            chunk_overlap_tokens=settings.chunk_overlap_tokens,
        )

        if not chunks:
            raise ValueError("No extractable text found in this file.")

        embedding_provider = get_embedding_provider()
        vector_store = get_vector_store()
        vector_store.ensure_collection(embedding_provider.dimension)

        texts = [c.text for c in chunks]
        vectors = embedding_provider.embed_texts(texts)

        document_chunk_repository.delete_by_file_id(db, file.tenant_id, file.id)

        chunk_rows: list[DocumentChunk] = []
        points: list[ChunkPoint] = []
        total_text_length = 0
        for index, (chunk, vector) in enumerate(zip(chunks, vectors, strict=True)):
            chunk_id = uuid.uuid4()
            content_hash = hashlib.sha256(chunk.text.encode()).hexdigest()
            total_text_length += len(chunk.text)
            chunk_rows.append(
                DocumentChunk(
                    id=chunk_id,
                    tenant_id=file.tenant_id,
                    knowledge_base_id=file.knowledge_base_id,
                    file_id=file.id,
                    chunk_index=index,
                    content=chunk.text,
                    content_hash=content_hash,
                    page_number=chunk.page_number,
                    section_title=chunk.section_title,
                    token_count=len(chunk.text.split()),
                )
            )
            points.append(
                ChunkPoint(
                    chunk_id=chunk_id,
                    vector=vector,
                    payload={
                        "tenant_id": str(file.tenant_id),
                        "knowledge_base_id": str(file.knowledge_base_id),
                        "file_id": str(file.id),
                        "file_name": file.original_name,
                        "chunk_index": index,
                        "page_number": chunk.page_number,
                        "section_title": chunk.section_title,
                        "checksum": content_hash,
                    },
                )
            )

        document_chunk_repository.bulk_create(db, chunk_rows)
        vector_store.upsert_chunks(points)

        file_repository.update_status(
            db,
            file,
            status=STATUS_COMPLETED,
            page_count=page_count,
            extracted_text_length=total_text_length,
            processed_at=datetime.now(UTC),
        )
        record_audit_event(
            db,
            action=AUDIT_FILE_PROCESSED,
            tenant_id=file.tenant_id,
            resource_type="file",
            resource_id=file.id,
            details={"chunk_count": len(chunk_rows), "page_count": page_count},
        )
    except Exception as exc:  # noqa: BLE001 -- any processing failure marks the file failed, never crashes the worker
        file_repository.update_status(
            db, file, status=STATUS_FAILED, error=f"{type(exc).__name__}: processing failed"
        )
        record_audit_event(
            db,
            action=AUDIT_FILE_PROCESSING_FAILED,
            tenant_id=file.tenant_id,
            resource_type="file",
            resource_id=file.id,
            details={"error_type": type(exc).__name__},
        )
