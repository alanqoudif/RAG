"""Merges approved database and document outputs into evidence for the answer generator, and
builds the citation list. Only successfully validated+executed SQL and retrieved chunks become
evidence — a rejected/failed query never reaches the LLM as "fact."
"""

from app.agents.state import ChatState
from app.core.constants import CITATION_TYPE_DATABASE
from app.services.chat.answer_generator import generate_answer
from app.services.documents.citation_service import format_document_citation


async def merge_and_generate(state: ChatState) -> ChatState:
    database_evidence: list[dict] = []
    citations: list[dict] = []

    for outcome in state.sql_outcomes:
        execution = outcome.execution_result
        if execution is not None and execution.ok:
            database_evidence.append(
                {
                    "sql": outcome.query_execution.normalized_sql,
                    "rows": execution.rows[:20],
                }
            )
            citations.append(
                {
                    "type": CITATION_TYPE_DATABASE,
                    "query_execution_id": str(outcome.query_execution.id),
                    "tables": outcome.query_execution.referenced_tables,
                }
            )
            state.sources_used.append("database")

    document_evidence: list[dict] = []
    for chunk in state.doc_results:
        document_evidence.append(
            {
                "file_name": chunk.file_name,
                "page_number": chunk.page_number,
                "content": chunk.content,
            }
        )
        citations.append(format_document_citation(chunk))
    if state.doc_results:
        state.sources_used.append("documents")

    state.citations = citations
    state.answer = await generate_answer(
        state.ollama_client,
        question=state.question,
        database_evidence=database_evidence,
        document_evidence=document_evidence,
    )
    return state
