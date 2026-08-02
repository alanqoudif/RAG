import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.config import get_settings
from app.repositories import refresh_token_repository


def issue_refresh_token(db: Session, *, tenant_id: uuid.UUID, user_id: uuid.UUID) -> str:
    settings = get_settings()
    raw_token = secrets.token_urlsafe(48)
    expires_at = datetime.now(UTC) + timedelta(days=settings.refresh_token_expire_days)
    refresh_token_repository.create(
        db, tenant_id=tenant_id, user_id=user_id, raw_token=raw_token, expires_at=expires_at
    )
    return raw_token


def rotate_refresh_token(db: Session, *, raw_token: str) -> tuple[str, uuid.UUID, uuid.UUID] | None:
    """Validate and consume a refresh token, returning (new_raw_token, tenant_id, user_id) or None."""
    existing = refresh_token_repository.get_active_by_raw_token(db, raw_token)
    if existing is None or not existing.is_active:
        return None
    if existing.expires_at.replace(tzinfo=UTC) < datetime.now(UTC):
        return None

    new_raw_token = issue_refresh_token(db, tenant_id=existing.tenant_id, user_id=existing.user_id)
    new_token = refresh_token_repository.get_active_by_raw_token(db, new_raw_token)
    refresh_token_repository.revoke(db, existing, replaced_by_id=new_token.id if new_token else None)
    return new_raw_token, existing.tenant_id, existing.user_id
