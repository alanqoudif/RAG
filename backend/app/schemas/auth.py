import uuid

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    tenant_code: str = Field(..., examples=["acme"])
    email: EmailStr
    password: str = Field(..., min_length=1)


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class CurrentUserResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    email: str
    is_tenant_admin: bool
    roles: list[str]
