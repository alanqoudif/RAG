import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ConversationCreateRequest(BaseModel):
    title: str | None = None


class ConversationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    user_id: uuid.UUID
    title: str | None
    status: str
    created_at: datetime
    last_message_at: datetime | None


class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    conversation_id: uuid.UUID
    role: str
    content: str
    detected_intent: str | None
    selected_sources: list | dict
    created_at: datetime


class CitationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    citation_type: str
    file_id: uuid.UUID | None
    chunk_id: uuid.UUID | None
    query_execution_id: uuid.UUID | None
    title: str | None
    source_reference: str | None
    page_number: int | None
    relevance_score: float | None


class SqlDetailResponse(BaseModel):
    query_execution_id: uuid.UUID
    generated_sql: str
    normalized_sql: str | None
    validation_status: str
    execution_status: str | None
    row_count: int | None
