import json
import uuid

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.tenant_context import CurrentUser
from app.dependencies import get_current_user, get_db
from app.repositories import query_execution_repository
from app.schemas.chat import ChatRequest, ChatResponse, SqlSummary
from app.services.chat.chat_service import handle_chat_request
from app.services.llm.ollama_client import OllamaClient

router = APIRouter(prefix="/chat", tags=["chat"])


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _sql_summary(db: Session, tenant_id: uuid.UUID, message_id: uuid.UUID) -> SqlSummary | None:
    executions = query_execution_repository.list_by_message_id(db, tenant_id, message_id)
    passed = [e for e in executions if e.execution_status == "success"]
    if not passed:
        return None
    execution = passed[0]
    return SqlSummary(
        query_execution_id=execution.id,
        query=execution.normalized_sql or execution.generated_sql,
        row_count=execution.returned_row_count or 0,
    )


@router.post("", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> ChatResponse:
    ollama_client = OllamaClient(get_settings())
    result = await handle_chat_request(
        db,
        current_user=current_user,
        question=payload.message,
        database_connection_ids=payload.database_connection_ids,
        knowledge_base_ids=payload.knowledge_base_ids,
        conversation_id=payload.conversation_id,
        ollama_client=ollama_client,
        ip_address=_client_ip(request),
        request_id=getattr(request.state, "request_id", None),
    )
    citations = [c.citation_metadata for c in result.message.citations]
    return ChatResponse(
        message_id=result.message.id,
        conversation_id=result.conversation_id,
        answer=result.message.content,
        intent=result.intent,
        sources_used=result.sources_used,
        sql=_sql_summary(db, current_user.tenant_id, result.message.id),
        citations=citations,
    )


def _sse_event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@router.post("/stream")
async def chat_stream(
    payload: ChatRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> StreamingResponse:
    async def event_generator():
        try:
            yield _sse_event("status", {"stage": "classifying_request"})
            ollama_client = OllamaClient(get_settings())
            result = await handle_chat_request(
                db,
                current_user=current_user,
                question=payload.message,
                database_connection_ids=payload.database_connection_ids,
                knowledge_base_ids=payload.knowledge_base_ids,
                conversation_id=payload.conversation_id,
                ollama_client=ollama_client,
                ip_address=_client_ip(request),
                request_id=getattr(request.state, "request_id", None),
            )

            yield _sse_event("intent", {"intent": result.intent})
            for source in result.sources_used:
                yield _sse_event("source", {"source": source})

            sql_summary = _sql_summary(db, current_user.tenant_id, result.message.id)
            if sql_summary is not None:
                yield _sse_event(
                    "sql",
                    {
                        "query_execution_id": str(sql_summary.query_execution_id),
                        "query": sql_summary.query,
                        "row_count": sql_summary.row_count,
                    },
                )

            for citation in result.message.citations:
                yield _sse_event("citation", citation.citation_metadata)

            for word in result.message.content.split(" "):
                yield _sse_event("token", {"text": word + " "})

            yield _sse_event("completed", {"message_id": str(result.message.id)})
        except Exception:  # noqa: BLE001 -- never leak a stack trace over SSE
            yield _sse_event("error", {"code": "INTERNAL_ERROR", "message": "An unexpected error occurred."})

    return StreamingResponse(event_generator(), media_type="text/event-stream")
