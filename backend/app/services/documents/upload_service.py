import hashlib
import uuid
from pathlib import PurePosixPath

from sqlalchemy.orm import Session

from app.core.constants import MAX_UPLOAD_FILE_SIZE_BYTES, SUPPORTED_FILE_EXTENSIONS
from app.exceptions import ValidationAppError
from app.models.file import File
from app.repositories import file_repository
from app.storage.minio_client import get_object_storage


def validate_upload(original_name: str, data: bytes) -> str:
    extension = PurePosixPath(original_name).suffix.lower()
    if extension not in SUPPORTED_FILE_EXTENSIONS:
        raise ValidationAppError(
            f"Unsupported file type '{extension}'. Supported types: {sorted(SUPPORTED_FILE_EXTENSIONS)}"
        )
    if len(data) == 0:
        raise ValidationAppError("Uploaded file is empty.")
    if len(data) > MAX_UPLOAD_FILE_SIZE_BYTES:
        raise ValidationAppError(
            f"File exceeds the maximum allowed size of {MAX_UPLOAD_FILE_SIZE_BYTES} bytes."
        )
    return extension


def store_upload(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    uploaded_by: uuid.UUID,
    knowledge_base_id: uuid.UUID | None,
    original_name: str,
    data: bytes,
    content_type: str | None,
) -> File:
    extension = validate_upload(original_name, data)
    checksum = hashlib.sha256(data).hexdigest()
    stored_name = f"{uuid.uuid4()}{extension}"
    storage_path = f"{tenant_id}/{stored_name}"

    storage = get_object_storage()
    storage.put_object(storage_path, data, content_type)

    file = File(
        tenant_id=tenant_id,
        knowledge_base_id=knowledge_base_id,
        uploaded_by=uploaded_by,
        original_name=original_name,
        stored_name=stored_name,
        storage_path=storage_path,
        mime_type=content_type,
        extension=extension,
        file_size_bytes=len(data),
        checksum=checksum,
    )
    return file_repository.create(db, file)
