import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.core.tenant_context import CurrentUser
from app.services.llm.ollama_client import OllamaClient


@dataclass
class ChatState:
    """Typed state threaded through the LangGraph orchestration graph. Holds live objects (DB
    session, LLM client) alongside plain data — this is one generic graph shared by every
    tenant/connection/knowledge-base combination, never a per-table or per-tenant graph.
    """

    db: Session
    current_user: CurrentUser
    ollama_client: OllamaClient
    question: str
    database_connection_ids: list[uuid.UUID] = field(default_factory=list)
    knowledge_base_ids: list[uuid.UUID] = field(default_factory=list)
    conversation_id: uuid.UUID | None = None
    message_id: uuid.UUID | None = None
    ip_address: str | None = None
    request_id: str | None = None

    intent: str = ""
    sql_outcomes: list[Any] = field(default_factory=list)
    doc_results: list[Any] = field(default_factory=list)
    citations: list[dict] = field(default_factory=list)
    sources_used: list[str] = field(default_factory=list)
    answer: str = ""
    error: str | None = None
