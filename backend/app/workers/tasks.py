import uuid

from app.infrastructure.database import SessionLocal
from app.logging_config import get_logger
from app.repositories import file_repository
from app.workers.celery_app import celery_app

logger = get_logger(__name__)


@celery_app.task(name="app.workers.tasks.ping")
def ping() -> str:
    """Smoke-test task used by health checks and Phase 1 validation."""
    return "pong"


@celery_app.task(name="app.workers.tasks.process_file", bind=True, max_retries=0)
def process_file_task(self, tenant_id: str, file_id: str) -> str:
    """Runs the full parse/chunk/embed/index pipeline for one uploaded file. No automatic
    retries: a failed file is marked `failed` with a reason and can be reprocessed explicitly via
    POST /api/files/{id}/reprocess rather than silently retried against a still-broken input.
    """
    from app.services.documents.document_processor import process_file

    db = SessionLocal()
    try:
        file = file_repository.get_by_id(db, uuid.UUID(tenant_id), uuid.UUID(file_id))
        if file is None:
            logger.warning("process_file_task_file_not_found", file_id=file_id)
            return "not_found"
        process_file(db, file)
        return file.processing_status
    finally:
        db.close()
