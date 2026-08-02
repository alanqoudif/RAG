import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.constants import AUDIT_CONNECTION_TESTED, STATUS_ACTIVE, STATUS_FAILED
from app.models.database_connection import DatabaseConnection
from app.repositories import database_connection_repository
from app.services.audit_service import record_audit_event
from app.services.database.adapters.base import ConnectionTestResult
from app.services.database.connection_service import to_connection_details
from app.services.database.dialect_resolver import get_adapter


def test_connection(
    db: Session,
    connection: DatabaseConnection,
    *,
    user_id: uuid.UUID,
    ip_address: str | None = None,
    request_id: str | None = None,
) -> ConnectionTestResult:
    adapter = get_adapter(connection.database_type)
    details = to_connection_details(connection)
    result = adapter.test_connection(details)

    status = STATUS_ACTIVE if result.ok else STATUS_FAILED
    database_connection_repository.record_test_result(
        db, connection, status=status, message=result.message, tested_at=datetime.now(UTC)
    )
    record_audit_event(
        db,
        action=AUDIT_CONNECTION_TESTED,
        tenant_id=connection.tenant_id,
        user_id=user_id,
        resource_type="database_connection",
        resource_id=connection.id,
        ip_address=ip_address,
        request_id=request_id,
        details={"database_type": connection.database_type, "ok": result.ok},
    )
    return result
