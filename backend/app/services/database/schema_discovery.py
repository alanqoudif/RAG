import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.constants import AUDIT_SCHEMA_SYNCED, STATUS_COMPLETED, STATUS_FAILED
from app.models.database_connection import DatabaseConnection
from app.repositories import database_schema_repository
from app.services.audit_service import record_audit_event
from app.services.database.connection_service import to_connection_details
from app.services.database.dialect_resolver import get_adapter


def sync_schema(
    db: Session,
    connection: DatabaseConnection,
    *,
    user_id: uuid.UUID,
    ip_address: str | None = None,
    request_id: str | None = None,
) -> None:
    adapter = get_adapter(connection.database_type)
    details = to_connection_details(connection)
    outcome: dict[str, object]

    try:
        discovered = adapter.discover_schemas(details)
        database_schema_repository.replace_discovered_schema(
            db,
            tenant_id=connection.tenant_id,
            connection_id=connection.id,
            discovered_schemas=discovered,
        )
        connection.schema_sync_status = STATUS_COMPLETED
        table_count = sum(len(s.tables) for s in discovered)
        outcome = {"schema_count": len(discovered), "table_count": table_count, "ok": True}
    except Exception as exc:  # noqa: BLE001 -- any discovery failure marks sync failed, never propagates driver internals
        connection.schema_sync_status = STATUS_FAILED
        outcome = {"ok": False, "error_type": type(exc).__name__}

    connection.last_schema_sync_at = datetime.now(UTC)
    db.add(connection)
    db.commit()

    record_audit_event(
        db,
        action=AUDIT_SCHEMA_SYNCED,
        tenant_id=connection.tenant_id,
        user_id=user_id,
        resource_type="database_connection",
        resource_id=connection.id,
        ip_address=ip_address,
        request_id=request_id,
        details=outcome,
    )
