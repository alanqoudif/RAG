import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class FileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    knowledge_base_id: uuid.UUID | None
    original_name: str
    mime_type: str | None
    extension: str | None
    file_size_bytes: int | None
    checksum: str | None
    processing_status: str
    processing_error: str | None
    page_count: int | None
    extracted_text_length: int | None
    created_at: datetime
    processed_at: datetime | None
