"""Qdrant wrapper. Every search is mandatorily filtered by tenant_id and the caller-supplied set
of allowed knowledge_base_ids — there is no code path that queries Qdrant without both filters,
which is what prevents cross-tenant retrieval regardless of what the LLM asks for.
"""

import uuid
from dataclasses import dataclass
from functools import lru_cache

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from app.config import Settings, get_settings


@dataclass
class ChunkPoint:
    chunk_id: uuid.UUID
    vector: list[float]
    payload: dict


@dataclass
class SearchHit:
    chunk_id: uuid.UUID
    score: float
    payload: dict


class VectorStore:
    def __init__(self, settings: Settings):
        self._settings = settings
        self._client = QdrantClient(url=settings.qdrant_url)
        self._collection = settings.qdrant_collection

    def ensure_collection(self, dimension: int) -> None:
        existing = [c.name for c in self._client.get_collections().collections]
        if self._collection in existing:
            return
        self._client.create_collection(
            collection_name=self._collection,
            vectors_config=qmodels.VectorParams(size=dimension, distance=qmodels.Distance.COSINE),
        )

    def upsert_chunks(self, points: list[ChunkPoint]) -> None:
        if not points:
            return
        self._client.upsert(
            collection_name=self._collection,
            points=[
                qmodels.PointStruct(id=str(p.chunk_id), vector=p.vector, payload=p.payload)
                for p in points
            ],
        )

    def delete_by_file_id(self, tenant_id: uuid.UUID, file_id: uuid.UUID) -> None:
        self._client.delete(
            collection_name=self._collection,
            points_selector=qmodels.FilterSelector(
                filter=qmodels.Filter(
                    must=[
                        qmodels.FieldCondition(
                            key="tenant_id", match=qmodels.MatchValue(value=str(tenant_id))
                        ),
                        qmodels.FieldCondition(
                            key="file_id", match=qmodels.MatchValue(value=str(file_id))
                        ),
                    ]
                )
            ),
        )

    def search(
        self,
        query_vector: list[float],
        *,
        tenant_id: uuid.UUID,
        knowledge_base_ids: list[uuid.UUID],
        top_k: int = 5,
    ) -> list[SearchHit]:
        if not knowledge_base_ids:
            return []
        must_conditions: list[qmodels.Condition] = [
            qmodels.FieldCondition(key="tenant_id", match=qmodels.MatchValue(value=str(tenant_id))),
            qmodels.FieldCondition(
                key="knowledge_base_id",
                match=qmodels.MatchAny(any=[str(kb_id) for kb_id in knowledge_base_ids]),
            ),
        ]
        results = self._client.query_points(
            collection_name=self._collection,
            query=query_vector,
            query_filter=qmodels.Filter(must=must_conditions),
            limit=top_k,
        ).points
        return [
            SearchHit(chunk_id=uuid.UUID(str(r.id)), score=r.score, payload=r.payload or {})
            for r in results
        ]


@lru_cache
def get_vector_store() -> VectorStore:
    return VectorStore(get_settings())
