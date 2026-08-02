import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.constants import SUPPORTED_DB_TYPES


class DatabaseConnectionCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    database_type: str = Field(..., examples=list(SUPPORTED_DB_TYPES))

    @field_validator("database_type")
    @classmethod
    def _validate_database_type(cls, v: str) -> str:
        if v not in SUPPORTED_DB_TYPES:
            raise ValueError(f"database_type must be one of {SUPPORTED_DB_TYPES}")
        return v
    host: str | None = None
    port: int | None = None
    database_name: str | None = None
    username: str | None = None
    password: str | None = None
    ssl_enabled: bool = False
    connection_options: dict = Field(default_factory=dict)


class DatabaseConnectionUpdateRequest(BaseModel):
    name: str | None = None
    host: str | None = None
    port: int | None = None
    database_name: str | None = None
    username: str | None = None
    password: str | None = None
    ssl_enabled: bool | None = None
    connection_options: dict | None = None


class DatabaseConnectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    database_type: str
    host: str | None
    port: int | None
    database_name: str | None
    username: str | None
    ssl_enabled: bool
    status: str
    last_tested_at: datetime | None
    last_test_message: str | None
    schema_sync_status: str
    last_schema_sync_at: datetime | None
    is_active: bool
    created_at: datetime


class ConnectionTestResponse(BaseModel):
    ok: bool
    message: str


class DatabaseColumnResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    column_name: str
    data_type: str
    is_nullable: bool | None
    is_primary_key: bool
    is_foreign_key: bool
    referenced_schema: str | None
    referenced_table: str | None
    referenced_column: str | None


class DatabaseTableResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    table_name: str
    table_type: str
    estimated_row_count: int | None
    primary_key_columns: list[str]
    columns: list[DatabaseColumnResponse] = Field(default_factory=list)


class DatabaseSchemaResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    schema_name: str
