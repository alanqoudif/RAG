"""Document RAG retrieval: embed the query, search Qdrant (always tenant + knowledge-base
filtered), optionally rerank, and join back to the platform DB for the full chunk content and
citation metadata. Qdrant alone can never be queried without both filters — see
app.vector_store.qdrant_store.VectorStore.search.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.repositories import document_chunk_repository
from app.services.documents.embedding_service import get_embedding_provider
from app.services.documents.reranker_service import get_reranker
from app.vector_store.qdrant_store import get_vector_store


@dataclass
class RetrievedChunk:
    chunk_id: uuid.UUID
    file_id: uuid.UUID
    file_name: str
    content: str
    page_number: int | None
    section_title: str | None
    score: float


def retrieve(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    knowledge_base_ids: list[uuid.UUID],
    query: str,
    settings: Settings | None = None,
) -> list[RetrievedChunk]:
    settings = settings or get_settings()
    if not knowledge_base_ids or not query.strip():
        return []

    provider = get_embedding_provider()
    query_vector = provider.embed_query(query)

    store = get_vector_store()
    hits = store.search(
        query_vector,
        tenant_id=tenant_id,
        knowledge_base_ids=knowledge_base_ids,
        top_k=settings.retrieval_top_k,
    )
    if not hits:
        return []

    chunk_ids = [h.chunk_id for h in hits]
    chunks = document_chunk_repository.get_by_ids(db, tenant_id, chunk_ids)
    chunk_map = {c.id: c for c in chunks}

    results: list[RetrievedChunk] = []
    for hit in hits:
        chunk = chunk_map.get(hit.chunk_id)
        if chunk is None:
            continue
        results.append(
            RetrievedChunk(
                chunk_id=chunk.id,
                file_id=chunk.file_id,
                file_name=hit.payload.get("file_name", ""),
                content=chunk.content,
                page_number=chunk.page_number,
                section_title=chunk.section_title,
                score=hit.score,
            )
        )

    reranker = get_reranker(settings)
    if reranker is not None and results:
        scores = reranker.rerank(query, [r.content for r in results])
        for result, score in zip(results, scores, strict=True):
            result.score = score
        results.sort(key=lambda r: r.score, reverse=True)

    return results
