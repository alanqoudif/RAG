import hashlib
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.refresh_token import RefreshToken


def hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode()).hexdigest()


def create(
    db: Session, *, tenant_id: uuid.UUID, user_id: uuid.UUID, raw_token: str, expires_at: datetime
) -> RefreshToken:
    token = RefreshToken(
        tenant_id=tenant_id,
        user_id=user_id,
        token_hash=hash_token(raw_token),
        expires_at=expires_at,
    )
    db.add(token)
    db.commit()
    db.refresh(token)
    return token


def get_active_by_raw_token(db: Session, raw_token: str) -> RefreshToken | None:
    token_hash = hash_token(raw_token)
    return db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    ).scalar_one_or_none()


def revoke(db: Session, token: RefreshToken, *, replaced_by_id: uuid.UUID | None = None) -> None:
    token.revoked_at = datetime.now(UTC)
    if replaced_by_id is not None:
        token.replaced_by_id = replaced_by_id
    db.add(token)
    db.commit()


def revoke_all_for_user(db: Session, tenant_id: uuid.UUID, user_id: uuid.UUID) -> None:
    tokens = db.execute(
        select(RefreshToken).where(
            RefreshToken.tenant_id == tenant_id,
            RefreshToken.user_id == user_id,
            RefreshToken.revoked_at.is_(None),
        )
    ).scalars()
    now = datetime.now(UTC)
    for token in tokens:
        token.revoked_at = now
        db.add(token)
    db.commit()
