import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog

# Fields that must never be written to audit details, even if a caller passes them by mistake.
_FORBIDDEN_DETAIL_KEYS = {
    "password",
    "password_hash",
    "encrypted_password",
    "encrypted_connection_string",
    "connection_string",
    "access_token",
    "refresh_token",
    "jwt_secret_key",
    "encryption_key",
}


def _sanitize(details: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in details.items() if k.lower() not in _FORBIDDEN_DETAIL_KEYS}


def record_audit_event(
    db: Session,
    *,
    action: str,
    tenant_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    resource_type: str | None = None,
    resource_id: uuid.UUID | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    request_id: str | None = None,
    details: dict[str, Any] | None = None,
) -> AuditLog:
    entry = AuditLog(
        tenant_id=tenant_id,
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        ip_address=ip_address,
        user_agent=user_agent,
        request_id=request_id,
        details=_sanitize(details or {}),
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry
