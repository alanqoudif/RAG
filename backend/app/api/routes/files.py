import uuid

from fastapi import APIRouter, Depends, File as FastAPIFile, Form, UploadFile
from sqlalchemy.orm import Session

from app.core.constants import AUDIT_FILE_UPLOADED, STATUS_PENDING
from app.core.tenant_context import CurrentUser
from app.dependencies import get_current_user, get_db
from app.exceptions import NotFoundError
from app.repositories import file_repository
from app.schemas.file import FileResponse
from app.services.audit_service import record_audit_event
from app.services.documents import upload_service
from app.storage.minio_client import get_object_storage
from app.vector_store.qdrant_store import get_vector_store
from app.workers.tasks import process_file_task

router = APIRouter(prefix="/files", tags=["files"])


def _get_owned_file(db: Session, current_user: CurrentUser, file_id: uuid.UUID):
    file = file_repository.get_by_id(db, current_user.tenant_id, file_id)
    if file is None:
        raise NotFoundError("File not found.")
    return file


@router.get("", response_model=list[FileResponse])
def list_files(
    knowledge_base_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[FileResponse]:
    files = file_repository.list_by_tenant(db, current_user.tenant_id, knowledge_base_id=knowledge_base_id)
    return [FileResponse.model_validate(f) for f in files]


@router.post("/upload", response_model=FileResponse, status_code=201)
async def upload_file(
    upload: UploadFile = FastAPIFile(...),
    knowledge_base_id: uuid.UUID | None = Form(default=None),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> FileResponse:
    data = await upload.read()
    file = upload_service.store_upload(
        db,
        tenant_id=current_user.tenant_id,
        uploaded_by=current_user.id,
        knowledge_base_id=knowledge_base_id,
        original_name=upload.filename or "unnamed",
        data=data,
        content_type=upload.content_type,
    )
    record_audit_event(
        db,
        action=AUDIT_FILE_UPLOADED,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        resource_type="file",
        resource_id=file.id,
        details={"original_name": file.original_name, "size_bytes": file.file_size_bytes},
    )
    process_file_task.delay(str(current_user.tenant_id), str(file.id))
    return FileResponse.model_validate(file)


@router.get("/{file_id}", response_model=FileResponse)
def get_file(
    file_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> FileResponse:
    file = _get_owned_file(db, current_user, file_id)
    return FileResponse.model_validate(file)


@router.delete("/{file_id}", status_code=204)
def delete_file(
    file_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> None:
    file = _get_owned_file(db, current_user, file_id)

    try:
        get_object_storage().delete_object(file.storage_path)
    except Exception:  # noqa: BLE001 -- object may already be gone; DB row deletion still proceeds
        pass
    get_vector_store().delete_by_file_id(current_user.tenant_id, file.id)
    file_repository.delete(db, file)


@router.post("/{file_id}/reprocess", response_model=FileResponse)
def reprocess_file(
    file_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> FileResponse:
    file = _get_owned_file(db, current_user, file_id)
    file = file_repository.update_status(db, file, status=STATUS_PENDING)
    process_file_task.delay(str(current_user.tenant_id), str(file.id))
    return FileResponse.model_validate(file)
