from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.permissions import require_tenant_admin
from app.core.tenant_context import CurrentUser
from app.dependencies import get_db
from app.repositories import audit_repository
from app.schemas.audit import AuditLogResponse

router = APIRouter(prefix="/audit-logs", tags=["audit"])


@router.get("", response_model=list[AuditLogResponse])
def list_audit_logs(
    limit: int = Query(default=100, le=500),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_tenant_admin()),
) -> list[AuditLogResponse]:
    logs = audit_repository.list_by_tenant(db, current_user.tenant_id, limit=limit)
    return [AuditLogResponse.model_validate(log) for log in logs]
