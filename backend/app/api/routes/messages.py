import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.tenant_context import CurrentUser
from app.dependencies import get_current_user, get_db
from app.exceptions import NotFoundError
from app.repositories import (
    message_citation_repository,
    message_repository,
    query_execution_repository,
)
from app.schemas.conversation import CitationResponse, SqlDetailResponse

router = APIRouter(prefix="/messages", tags=["messages"])


def _ensure_message_owned(db: Session, current_user: CurrentUser, message_id: uuid.UUID):
    message = message_repository.get_by_id(db, current_user.tenant_id, message_id)
    if message is None:
        raise NotFoundError("Message not found.")
    return message


@router.get("/{message_id}/citations", response_model=list[CitationResponse])
def get_message_citations(
    message_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[CitationResponse]:
    _ensure_message_owned(db, current_user, message_id)
    citations = message_citation_repository.list_by_message(db, current_user.tenant_id, message_id)
    return [CitationResponse.model_validate(c) for c in citations]


@router.get("/{message_id}/sql", response_model=list[SqlDetailResponse])
def get_message_sql(
    message_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[SqlDetailResponse]:
    _ensure_message_owned(db, current_user, message_id)
    executions = query_execution_repository.list_by_message_id(db, current_user.tenant_id, message_id)
    return [
        SqlDetailResponse(
            query_execution_id=e.id,
            generated_sql=e.generated_sql,
            normalized_sql=e.normalized_sql,
            validation_status=e.validation_status,
            execution_status=e.execution_status,
            row_count=e.returned_row_count,
        )
        for e in executions
    ]
