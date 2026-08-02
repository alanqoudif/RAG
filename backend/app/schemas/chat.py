import uuid

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    conversation_id: uuid.UUID | None = None
    message: str = Field(..., min_length=1)
    database_connection_ids: list[uuid.UUID] = Field(default_factory=list)
    knowledge_base_ids: list[uuid.UUID] = Field(default_factory=list)
    stream: bool = False


class SqlSummary(BaseModel):
    query_execution_id: uuid.UUID
    query: str
    row_count: int


class ChatResponse(BaseModel):
    message_id: uuid.UUID
    conversation_id: uuid.UUID
    answer: str
    intent: str
    sources_used: list[str]
    sql: SqlSummary | None = None
    citations: list[dict] = Field(default_factory=list)
