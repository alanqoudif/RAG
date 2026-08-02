"""Top-level chat entry point: resolves/creates the conversation, saves the user message, runs
the orchestration graph, saves the assistant message + citations, and records the chat_request
audit event. Both POST /api/chat and POST /api/chat/stream call this (streaming just replays the
same result as SSE events instead of a single JSON body — the graph itself is not incremental).
"""

import time
import uuid

from sqlalchemy.orm import Session

from app.agents.graph import get_chat_graph
from app.agents.state import ChatState
from app.core.constants import AUDIT_CHAT_REQUEST, MESSAGE_ROLE_ASSISTANT, MESSAGE_ROLE_USER
from app.core.tenant_context import CurrentUser
from app.exceptions import NotFoundError
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.message_citation import MessageCitation
from app.repositories import conversation_repository, message_citation_repository, message_repository
from app.services.audit_service import record_audit_event
from app.services.llm.ollama_client import OllamaClient


class ChatResult:
    def __init__(self, *, message: Message, conversation_id: uuid.UUID, intent: str, sources_used: list[str]):
        self.message = message
        self.conversation_id = conversation_id
        self.intent = intent
        self.sources_used = sources_used


def _get_or_create_conversation(
    db: Session, *, current_user: CurrentUser, conversation_id: uuid.UUID | None
) -> Conversation:
    if conversation_id is not None:
        conversation = conversation_repository.get_by_id(db, current_user.tenant_id, conversation_id)
        if conversation is None:
            raise NotFoundError("Conversation not found.")
        return conversation
    conversation = Conversation(tenant_id=current_user.tenant_id, user_id=current_user.id)
    return conversation_repository.create(db, conversation)


async def handle_chat_request(
    db: Session,
    *,
    current_user: CurrentUser,
    question: str,
    database_connection_ids: list[uuid.UUID],
    knowledge_base_ids: list[uuid.UUID],
    conversation_id: uuid.UUID | None,
    ollama_client: OllamaClient,
    ip_address: str | None = None,
    request_id: str | None = None,
) -> ChatResult:
    conversation = _get_or_create_conversation(
        db, current_user=current_user, conversation_id=conversation_id
    )

    user_message = message_repository.create(
        db,
        Message(
            tenant_id=current_user.tenant_id,
            conversation_id=conversation.id,
            role=MESSAGE_ROLE_USER,
            content=question,
            selected_sources={
                "database_connection_ids": [str(i) for i in database_connection_ids],
                "knowledge_base_ids": [str(i) for i in knowledge_base_ids],
            },
        ),
    )

    started = time.perf_counter()
    state = ChatState(
        db=db,
        current_user=current_user,
        ollama_client=ollama_client,
        question=question,
        database_connection_ids=database_connection_ids,
        knowledge_base_ids=knowledge_base_ids,
        conversation_id=conversation.id,
        message_id=user_message.id,
        ip_address=ip_address,
        request_id=request_id,
    )

    graph = get_chat_graph()
    # LangGraph returns a plain dict of the state schema's fields, not a ChatState instance.
    result_dict: dict = await graph.ainvoke(state)
    result_state = ChatState(**{**state.__dict__, **result_dict})

    latency_ms = int((time.perf_counter() - started) * 1000)

    assistant_message = message_repository.create(
        db,
        Message(
            tenant_id=current_user.tenant_id,
            conversation_id=conversation.id,
            parent_message_id=user_message.id,
            role=MESSAGE_ROLE_ASSISTANT,
            content=result_state.answer,
            detected_intent=result_state.intent,
            selected_sources=list(set(result_state.sources_used)),
            model_name=ollama_client.settings.ollama_model,
            latency_ms=latency_ms,
        ),
    )

    # Re-point each QueryExecution at the assistant message (they were saved with the user
    # message's id, the only one that existed while the graph was running) so that
    # GET /api/messages/{assistant_message_id}/sql — the id actually returned to the caller —
    # resolves correctly.
    if result_state.sql_outcomes:
        for outcome in result_state.sql_outcomes:
            outcome.query_execution.message_id = assistant_message.id
            db.add(outcome.query_execution)
        db.commit()

    citation_rows = []
    for citation in result_state.citations:
        citation_rows.append(
            MessageCitation(
                tenant_id=current_user.tenant_id,
                message_id=assistant_message.id,
                citation_type=citation["type"],
                file_id=None,
                chunk_id=uuid.UUID(citation["chunk_id"]) if citation.get("chunk_id") else None,
                query_execution_id=(
                    uuid.UUID(citation["query_execution_id"])
                    if citation.get("query_execution_id")
                    else None
                ),
                title=citation.get("file_name"),
                source_reference=citation.get("section"),
                page_number=citation.get("page"),
                relevance_score=citation.get("relevance_score"),
                citation_metadata=citation,
            )
        )
    if citation_rows:
        message_citation_repository.bulk_create(db, citation_rows)

    conversation_repository.touch(db, conversation, at=assistant_message.created_at)

    record_audit_event(
        db,
        action=AUDIT_CHAT_REQUEST,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        resource_type="conversation",
        resource_id=conversation.id,
        ip_address=ip_address,
        request_id=request_id,
        details={"intent": result_state.intent, "sources_used": result_state.sources_used},
    )

    return ChatResult(
        message=assistant_message,
        conversation_id=conversation.id,
        intent=result_state.intent,
        sources_used=result_state.sources_used,
    )
