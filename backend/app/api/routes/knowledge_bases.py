import uuid

from fastapi import APIRouter, Depends, File as FastAPIFile, UploadFile
from sqlalchemy.orm import Session

from app.core.constants import AUDIT_FILE_UPLOADED
from app.core.tenant_context import CurrentUser
from app.dependencies import get_current_user, get_db
from app.exceptions import ConflictError, NotFoundError
from app.models.knowledge_base import KnowledgeBase
from app.repositories import knowledge_base_repository
from app.schemas.file import FileResponse
from app.schemas.knowledge_base import KnowledgeBaseCreateRequest, KnowledgeBaseResponse
from app.services.audit_service import record_audit_event
from app.services.documents import upload_service
from app.workers.tasks import process_file_task

router = APIRouter(prefix="/knowledge-bases", tags=["knowledge-bases"])


def _ensure_kb_owned(db: Session, current_user: CurrentUser, kb_id: uuid.UUID) -> KnowledgeBase:
    kb = knowledge_base_repository.get_by_id(db, current_user.tenant_id, kb_id)
    if kb is None:
        raise NotFoundError("Knowledge base not found.")
    return kb


@router.get("", response_model=list[KnowledgeBaseResponse])
def list_knowledge_bases(
    db: Session = Depends(get_db), current_user: CurrentUser = Depends(get_current_user)
) -> list[KnowledgeBaseResponse]:
    kbs = knowledge_base_repository.list_by_tenant(db, current_user.tenant_id)
    return [KnowledgeBaseResponse.model_validate(kb) for kb in kbs]


@router.post("", response_model=KnowledgeBaseResponse, status_code=201)
def create_knowledge_base(
    payload: KnowledgeBaseCreateRequest,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> KnowledgeBaseResponse:
    if knowledge_base_repository.get_by_name(db, current_user.tenant_id, payload.name) is not None:
        raise ConflictError("A knowledge base with this name already exists in this tenant.")
    kb = KnowledgeBase(
        tenant_id=current_user.tenant_id,
        created_by=current_user.id,
        name=payload.name,
        description=payload.description,
    )
    kb = knowledge_base_repository.create(db, kb)
    return KnowledgeBaseResponse.model_validate(kb)


@router.post("/{kb_id}/files", response_model=list[FileResponse], status_code=201)
async def upload_files_to_knowledge_base(
    kb_id: uuid.UUID,
    uploads: list[UploadFile] = FastAPIFile(...),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[FileResponse]:
    kb = _ensure_kb_owned(db, current_user, kb_id)
    created: list[FileResponse] = []

    for upload in uploads:
        data = await upload.read()
        file = upload_service.store_upload(
            db,
            tenant_id=current_user.tenant_id,
            uploaded_by=current_user.id,
            knowledge_base_id=kb.id,
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
        created.append(FileResponse.model_validate(file))

    return created
