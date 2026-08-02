import uuid
from collections.abc import Generator

from fastapi import Depends, Header
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.core.tenant_context import CurrentUser
from app.exceptions import UnauthorizedError
from app.infrastructure.database import get_db as _get_db
from app.repositories import user_repository

get_db = _get_db


def get_session() -> Generator[Session, None, None]:
    yield from _get_db()


def get_current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> CurrentUser:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise UnauthorizedError("Missing or malformed Authorization header.")

    token = authorization.split(" ", 1)[1].strip()
    claims = decode_access_token(token)

    user = user_repository.get_by_id(db, uuid.UUID(claims.tenant_id), uuid.UUID(claims.user_id))
    if user is None or not user.is_active:
        raise UnauthorizedError("User account is inactive or no longer exists.")

    roles = frozenset(r.name for r in user_repository.get_roles(db, user.tenant_id, user.id))
    return CurrentUser(
        id=user.id,
        tenant_id=user.tenant_id,
        email=user.email,
        is_tenant_admin=user.is_tenant_admin,
        roles=roles,
    )
