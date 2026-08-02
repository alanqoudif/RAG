"""Embedding provider behind an interface so the model can be swapped (e.g. `bge-small-en-v1.5`
for speed, `bge-m3` for stronger multilingual/Arabic support) purely through configuration.
"""

from abc import ABC, abstractmethod
from functools import lru_cache

from app.config import Settings, get_settings


class EmbeddingProvider(ABC):
    @property
    @abstractmethod
    def dimension(self) -> int: ...

    @abstractmethod
    def embed_texts(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]:
        return self.embed_texts([text])[0]


class SentenceTransformerEmbeddingProvider(EmbeddingProvider):
    def __init__(self, model_name: str):
        from sentence_transformers import SentenceTransformer

        self._model_name = model_name
        self._model = SentenceTransformer(model_name)
        self._dimension = self._model.get_sentence_embedding_dimension()

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        vectors = self._model.encode(texts, normalize_embeddings=True)
        return [v.tolist() for v in vectors]


@lru_cache
def get_embedding_provider(settings: Settings | None = None) -> EmbeddingProvider:
    settings = settings or get_settings()
    return SentenceTransformerEmbeddingProvider(settings.embedding_model)
