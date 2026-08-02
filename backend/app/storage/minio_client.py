"""Thin wrapper around the MinIO SDK. Stores original uploaded files and nothing else — parsed
text/chunks live in the platform DB and Qdrant, never re-derived from re-reading MinIO on the
hot path.
"""

import io
from functools import lru_cache

from minio import Minio
from minio.error import S3Error

from app.config import Settings, get_settings
from app.logging_config import get_logger

logger = get_logger(__name__)


class ObjectStorage:
    def __init__(self, settings: Settings):
        self._settings = settings
        self._client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
        self._bucket = settings.minio_bucket

    def ensure_bucket(self) -> None:
        try:
            if not self._client.bucket_exists(self._bucket):
                self._client.make_bucket(self._bucket)
        except S3Error:
            logger.exception("minio_ensure_bucket_failed", bucket=self._bucket)
            raise

    def put_object(self, object_name: str, data: bytes, content_type: str | None) -> None:
        self._client.put_object(
            self._bucket,
            object_name,
            data=io.BytesIO(data),
            length=len(data),
            content_type=content_type or "application/octet-stream",
        )

    def get_object_bytes(self, object_name: str) -> bytes:
        response = self._client.get_object(self._bucket, object_name)
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()

    def delete_object(self, object_name: str) -> None:
        self._client.remove_object(self._bucket, object_name)


@lru_cache
def get_object_storage() -> ObjectStorage:
    storage = ObjectStorage(get_settings())
    storage.ensure_bucket()
    return storage
