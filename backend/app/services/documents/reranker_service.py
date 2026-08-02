"""Optional cross-encoder reranker (`BAAI/bge-reranker-base`), gated by `RERANKER_ENABLED`
(default off — it costs extra RAM/latency on top of the embedding model). Not exercised in this
session's automated tests for the same resource-budget reason as Docling; the retrieval path
works correctly with it disabled, which is also the documented default.
"""

from functools import lru_cache

from app.config import Settings, get_settings


class Reranker:
    def __init__(self, model_name: str):
        from sentence_transformers import CrossEncoder

        self._model = CrossEncoder(model_name)

    def rerank(self, query: str, documents: list[str]) -> list[float]:
        pairs = [[query, doc] for doc in documents]
        scores = self._model.predict(pairs)
        return [float(s) for s in scores]


@lru_cache
def get_reranker(settings: Settings | None = None) -> Reranker | None:
    settings = settings or get_settings()
    if not settings.reranker_enabled:
        return None
    return Reranker(settings.reranker_model)
