import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.tenant_context import CurrentUser
from app.dependencies import get_current_user, get_db
from app.exceptions import NotFoundError
from app.models.conversation import Conversation
from app.repositories import conversation_repository, message_repository
from app.schemas.conversation import ConversationCreateRequest, ConversationResponse, MessageResponse

router = APIRouter(prefix="/conversations", tags=["conversations"])


def _get_owned_conversation(db: Session, current_user: CurrentUser, conversation_id: uuid.UUID):
    conversation = conversation_repository.get_by_id(db, current_user.tenant_id, conversation_id)
    if conversation is None:
        raise NotFoundError("Conversation not found.")
    return conversation


@router.get("", response_model=list[ConversationResponse])
def list_conversations(
    db: Session = Depends(get_db), current_user: CurrentUser = Depends(get_current_user)
) -> list[ConversationResponse]:
    conversations = conversation_repository.list_by_user(db, current_user.tenant_id, current_user.id)
    return [ConversationResponse.model_validate(c) for c in conversations]


@router.post("", response_model=ConversationResponse, status_code=201)
def create_conversation(
    payload: ConversationCreateRequest,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> ConversationResponse:
    conversation = Conversation(
        tenant_id=current_user.tenant_id, user_id=current_user.id, title=payload.title
    )
    conversation = conversation_repository.create(db, conversation)
    return ConversationResponse.model_validate(conversation)


@router.get("/{conversation_id}", response_model=ConversationResponse)
def get_conversation(
    conversation_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> ConversationResponse:
    conversation = _get_owned_conversation(db, current_user, conversation_id)
    return ConversationResponse.model_validate(conversation)


@router.get("/{conversation_id}/messages", response_model=list[MessageResponse])
def list_messages(
    conversation_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[MessageResponse]:
    _get_owned_conversation(db, current_user, conversation_id)
    messages = message_repository.list_by_conversation(db, current_user.tenant_id, conversation_id)
    return [MessageResponse.model_validate(m) for m in messages]


@router.delete("/{conversation_id}", status_code=204)
def delete_conversation(
    conversation_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> None:
    conversation = _get_owned_conversation(db, current_user, conversation_id)
    conversation_repository.delete(db, conversation)
