from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.tenant_context import CurrentUser
from app.dependencies import get_current_user, get_db
from app.schemas.auth import CurrentUserResponse, LoginRequest, RefreshRequest, TokenResponse
from app.services.auth import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)) -> TokenResponse:
    pair = auth_service.login(
        db,
        tenant_code=payload.tenant_code,
        email=payload.email,
        password=payload.password,
        ip_address=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        request_id=getattr(request.state, "request_id", None),
    )
    return TokenResponse(access_token=pair.access_token, refresh_token=pair.refresh_token)


@router.post("/refresh", response_model=TokenResponse)
def refresh(payload: RefreshRequest, request: Request, db: Session = Depends(get_db)) -> TokenResponse:
    pair = auth_service.refresh(
        db,
        raw_refresh_token=payload.refresh_token,
        ip_address=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        request_id=getattr(request.state, "request_id", None),
    )
    return TokenResponse(access_token=pair.access_token, refresh_token=pair.refresh_token)


@router.get("/me", response_model=CurrentUserResponse)
def me(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUserResponse:
    return CurrentUserResponse(
        id=current_user.id,
        tenant_id=current_user.tenant_id,
        email=current_user.email,
        is_tenant_admin=current_user.is_tenant_admin,
        roles=sorted(current_user.roles),
    )
