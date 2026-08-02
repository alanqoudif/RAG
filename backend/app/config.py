from functools import lru_cache
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # App
    app_name: str = "text-to-sql-platform"
    environment: Literal["development", "test", "production"] = "development"
    debug: bool = False
    api_prefix: str = "/api"
    request_body_max_bytes: int = 25 * 1024 * 1024

    # Platform database
    database_url: str = (
        "postgresql+psycopg://platform:platform@localhost:5432/platform"
    )
    database_pool_size: int = 10
    database_max_overflow: int = 5

    # Auth
    jwt_secret_key: str = "change-me-in-env-this-is-not-secure"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 14

    # Encryption for stored DB credentials (Fernet key, 32 url-safe base64 bytes)
    encryption_key: str = "3sJf3pQd2Kk8m3v3wq5nD8oX2b6rP0y1c4h7l9a2f0E="

    # Redis / Celery
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"
    celery_concurrency: int = 1

    # MinIO / object storage
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_secure: bool = False
    minio_bucket: str = "documents"

    # Vector store
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "document_chunks"

    # LLM (Ollama)
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2:3b"
    ollama_fallback_model: str = "qwen3:4b"
    ollama_request_timeout_seconds: int = 120

    # Embeddings / reranking
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_dimension: int = 384
    reranker_enabled: bool = False
    reranker_model: str = "BAAI/bge-reranker-base"

    # Text-to-SQL limits
    sql_max_rows: int = 500
    sql_max_execution_seconds: int = 15
    sql_max_result_bytes: int = 2 * 1024 * 1024
    sql_max_columns: int = 50
    sql_max_joins: int = 6

    # Document processing
    chunk_size_tokens: int = 400
    chunk_overlap_tokens: int = 60
    allow_sample_values: bool = False
    sample_values_limit: int = 3

    # Seeding
    seed_on_startup: bool = False

    # Observability
    otel_enabled: bool = False
    log_level: str = "INFO"

    @field_validator("environment", mode="before")
    @classmethod
    def _lower(cls, v: str) -> str:
        return v.lower() if isinstance(v, str) else v


@lru_cache
def get_settings() -> Settings:
    return Settings()
