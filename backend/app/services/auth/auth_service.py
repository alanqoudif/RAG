from sqlalchemy.orm import Session

from app.core.constants import (
    AUDIT_LOGIN_FAILURE,
    AUDIT_LOGIN_SUCCESS,
    AUDIT_TOKEN_REFRESH,
    AUDIT_TOKEN_REFRESH_FAILURE,
)
from app.core.security import AccessTokenClaims, create_access_token, verify_password
from app.exceptions import UnauthorizedError
from app.models.user import User
from app.repositories import tenant_repository, user_repository
from app.services.audit_service import record_audit_event
from app.services.auth.token_service import issue_refresh_token, rotate_refresh_token


class TokenPair:
    def __init__(self, access_token: str, refresh_token: str, user: User):
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.user = user


def _issue_pair(db: Session, user: User) -> TokenPair:
    roles = [r.name for r in user_repository.get_roles(db, user.tenant_id, user.id)]
    access_token = create_access_token(
        AccessTokenClaims(
            user_id=str(user.id),
            tenant_id=str(user.tenant_id),
            email=user.email,
            is_tenant_admin=user.is_tenant_admin,
            roles=roles,
        )
    )
    refresh_token = issue_refresh_token(db, tenant_id=user.tenant_id, user_id=user.id)
    return TokenPair(access_token, refresh_token, user)


def login(
    db: Session,
    *,
    tenant_code: str,
    email: str,
    password: str,
    ip_address: str | None = None,
    user_agent: str | None = None,
    request_id: str | None = None,
) -> TokenPair:
    tenant = tenant_repository.get_by_code(db, tenant_code)
    user = user_repository.get_by_email(db, tenant.id, email) if tenant else None

    # Constant-shape failure path: don't reveal whether the tenant or the email was the problem.
    if tenant is None or user is None or not verify_password(password, user.password_hash):
        record_audit_event(
            db,
            action=AUDIT_LOGIN_FAILURE,
            tenant_id=tenant.id if tenant else None,
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id,
            details={"email": email, "tenant_code": tenant_code},
        )
        raise UnauthorizedError("Invalid credentials.")

    if not user.is_active:
        record_audit_event(
            db,
            action=AUDIT_LOGIN_FAILURE,
            tenant_id=tenant.id,
            user_id=user.id,
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id,
            details={"reason": "user_disabled"},
        )
        raise UnauthorizedError("This account is disabled.")

    pair = _issue_pair(db, user)
    record_audit_event(
        db,
        action=AUDIT_LOGIN_SUCCESS,
        tenant_id=user.tenant_id,
        user_id=user.id,
        ip_address=ip_address,
        user_agent=user_agent,
        request_id=request_id,
    )
    return pair


def refresh(
    db: Session,
    *,
    raw_refresh_token: str,
    ip_address: str | None = None,
    user_agent: str | None = None,
    request_id: str | None = None,
) -> TokenPair:
    rotated = rotate_refresh_token(db, raw_token=raw_refresh_token)
    if rotated is None:
        record_audit_event(
            db,
            action=AUDIT_TOKEN_REFRESH_FAILURE,
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id,
        )
        raise UnauthorizedError("Invalid or expired refresh token.")

    new_raw_token, tenant_id, user_id = rotated
    user = user_repository.get_by_id(db, tenant_id, user_id)
    if user is None or not user.is_active:
        raise UnauthorizedError("Invalid or expired refresh token.")

    roles = [r.name for r in user_repository.get_roles(db, tenant_id, user_id)]
    access_token = create_access_token(
        AccessTokenClaims(
            user_id=str(user.id),
            tenant_id=str(user.tenant_id),
            email=user.email,
            is_tenant_admin=user.is_tenant_admin,
            roles=roles,
        )
    )
    record_audit_event(
        db,
        action=AUDIT_TOKEN_REFRESH,
        tenant_id=tenant_id,
        user_id=user_id,
        ip_address=ip_address,
        user_agent=user_agent,
        request_id=request_id,
    )
    return TokenPair(access_token, new_raw_token, user)
