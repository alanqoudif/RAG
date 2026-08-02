import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.constants import AUDIT_PERMISSION_CHANGED
from app.core.permissions import require_tenant_admin
from app.core.tenant_context import CurrentUser
from app.dependencies import get_current_user, get_db
from app.exceptions import NotFoundError
from app.models.column_permission import ColumnPermission
from app.models.table_permission import TablePermission
from app.repositories import database_connection_repository, permission_repository
from app.schemas.permission import (
    AllowedSchemaResponse,
    TablePermissionCreateRequest,
    TablePermissionResponse,
)
from app.services.audit_service import record_audit_event
from app.services.database import permission_service

router = APIRouter(prefix="/database-connections/{connection_id}/permissions", tags=["permissions"])


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _get_owned_connection(db: Session, current_user: CurrentUser, connection_id: uuid.UUID):
    connection = database_connection_repository.get_by_id(db, current_user.tenant_id, connection_id)
    if connection is None:
        raise NotFoundError("Database connection not found.")
    return connection


@router.get("", response_model=list[TablePermissionResponse])
def list_permissions(
    connection_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_tenant_admin()),
) -> list[TablePermissionResponse]:
    _get_owned_connection(db, current_user, connection_id)
    grants = permission_repository.list_by_connection(db, current_user.tenant_id, connection_id)
    return [TablePermissionResponse.model_validate(g) for g in grants]


@router.post("", response_model=TablePermissionResponse, status_code=201)
def create_permission(
    connection_id: uuid.UUID,
    payload: TablePermissionCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_tenant_admin()),
) -> TablePermissionResponse:
    _get_owned_connection(db, current_user, connection_id)

    grant = TablePermission(
        tenant_id=current_user.tenant_id,
        role_id=payload.role_id,
        user_id=payload.user_id,
        connection_id=connection_id,
        table_id=payload.table_id,
        can_read=payload.can_read,
        can_insert=payload.can_insert,
        can_update=payload.can_update,
        can_delete=payload.can_delete,
        row_filter=payload.row_filter,
    )
    grant = permission_repository.create_table_permission(db, grant)

    for col in payload.column_permissions:
        permission_repository.create_column_permission(
            db,
            ColumnPermission(
                table_permission_id=grant.id,
                column_id=col.column_id,
                can_read=col.can_read,
                can_filter=col.can_filter,
                can_aggregate=col.can_aggregate,
                mask_type=col.mask_type,
            ),
        )
    db.refresh(grant)

    record_audit_event(
        db,
        action=AUDIT_PERMISSION_CHANGED,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        resource_type="table_permission",
        resource_id=grant.id,
        ip_address=_client_ip(request),
        request_id=getattr(request.state, "request_id", None),
        details={"connection_id": str(connection_id), "table_id": str(payload.table_id)},
    )
    return TablePermissionResponse.model_validate(grant)


@router.get("/allowed-schema", response_model=AllowedSchemaResponse)
def get_allowed_schema(
    connection_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> AllowedSchemaResponse:
    """What the current user's own permissions resolve to — the same shape the LLM prompt sees."""
    _get_owned_connection(db, current_user, connection_id)
    allowed_tables = permission_service.resolve_allowed_tables(
        db, connection_id=connection_id, current_user=current_user
    )
    return AllowedSchemaResponse(allowed_schema=permission_service.to_prompt_schema(allowed_tables))
