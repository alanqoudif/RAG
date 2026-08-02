import uuid

from pydantic import BaseModel, ConfigDict, Field


class RoleCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = None


class RoleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    description: str | None


class AssignRoleRequest(BaseModel):
    role_id: uuid.UUID
