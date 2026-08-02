import uuid

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ColumnPermissionInput(BaseModel):
    column_id: uuid.UUID
    can_read: bool = True
    can_filter: bool = True
    can_aggregate: bool = True
    mask_type: str | None = None


class TablePermissionCreateRequest(BaseModel):
    role_id: uuid.UUID | None = None
    user_id: uuid.UUID | None = None
    table_id: uuid.UUID
    can_read: bool = True
    can_insert: bool = False
    can_update: bool = False
    can_delete: bool = False
    row_filter: dict = Field(default_factory=dict)
    column_permissions: list[ColumnPermissionInput] = Field(default_factory=list)

    @model_validator(mode="after")
    def _exactly_one_subject(self) -> "TablePermissionCreateRequest":
        if (self.role_id is None) == (self.user_id is None):
            raise ValueError("Exactly one of role_id or user_id must be set.")
        return self


class ColumnPermissionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    column_id: uuid.UUID
    can_read: bool
    can_filter: bool
    can_aggregate: bool
    mask_type: str | None


class TablePermissionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    role_id: uuid.UUID | None
    user_id: uuid.UUID | None
    connection_id: uuid.UUID
    table_id: uuid.UUID
    can_read: bool
    can_insert: bool
    can_update: bool
    can_delete: bool
    row_filter: dict
    column_permissions: list[ColumnPermissionResponse] = Field(default_factory=list)


class AllowedSchemaResponse(BaseModel):
    allowed_schema: dict
