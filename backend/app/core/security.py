"""Password hashing (Argon2) and JWT access-token encode/decode.

Refresh tokens are handled separately (app.services.auth.token_service) as opaque, hashed,
server-side-revocable tokens rather than JWTs, so they can be rotated/invalidated on demand.
"""

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHash, VerificationError, VerifyMismatchError

from app.config import get_settings
from app.core.constants import TOKEN_TYPE_ACCESS
from app.exceptions import UnauthorizedError

_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHash):
        return False


def needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


@dataclass
class AccessTokenClaims:
    user_id: str
    tenant_id: str
    email: str
    is_tenant_admin: bool
    roles: list[str] = field(default_factory=list)


def create_access_token(claims: AccessTokenClaims) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    expires_at = now + timedelta(minutes=settings.access_token_expire_minutes)
    payload: dict[str, Any] = {
        "sub": claims.user_id,
        "tenant_id": claims.tenant_id,
        "email": claims.email,
        "is_tenant_admin": claims.is_tenant_admin,
        "roles": claims.roles,
        "type": TOKEN_TYPE_ACCESS,
        "iat": now,
        "exp": expires_at,
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> AccessTokenClaims:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except jwt.ExpiredSignatureError as exc:
        raise UnauthorizedError("Access token has expired.") from exc
    except jwt.InvalidTokenError as exc:
        raise UnauthorizedError("Invalid access token.") from exc

    if payload.get("type") != TOKEN_TYPE_ACCESS:
        raise UnauthorizedError("Invalid access token.")

    return AccessTokenClaims(
        user_id=payload["sub"],
        tenant_id=payload["tenant_id"],
        email=payload["email"],
        is_tenant_admin=payload.get("is_tenant_admin", False),
        roles=payload.get("roles", []),
    )
