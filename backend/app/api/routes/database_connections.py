import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.core.constants import (
    AUDIT_CONNECTION_CREATED,
    AUDIT_CONNECTION_DELETED,
    AUDIT_CONNECTION_UPDATED,
)
from app.core.permissions import require_tenant_admin
from app.core.tenant_context import CurrentUser
from app.dependencies import get_current_user, get_db
from app.exceptions import NotFoundError
from app.repositories import database_connection_repository, database_schema_repository
from app.schemas.database_connection import (
    ConnectionTestResponse,
    DatabaseConnectionCreateRequest,
    DatabaseConnectionResponse,
    DatabaseConnectionUpdateRequest,
    DatabaseSchemaResponse,
    DatabaseTableResponse,
)
from app.services.audit_service import record_audit_event
from app.services.database import connection_service, connection_tester, schema_discovery

router = APIRouter(prefix="/database-connections", tags=["database-connections"])


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _get_owned_connection(db: Session, current_user: CurrentUser, connection_id: uuid.UUID):
    connection = database_connection_repository.get_by_id(db, current_user.tenant_id, connection_id)
    if connection is None:
        raise NotFoundError("Database connection not found.")
    return connection


@router.get("", response_model=list[DatabaseConnectionResponse])
def list_connections(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[DatabaseConnectionResponse]:
    connections = database_connection_repository.list_by_tenant(db, current_user.tenant_id)
    return [DatabaseConnectionResponse.model_validate(c) for c in connections]


@router.post("", response_model=DatabaseConnectionResponse, status_code=201)
def create_connection(
    payload: DatabaseConnectionCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_tenant_admin()),
) -> DatabaseConnectionResponse:
    connection = connection_service.create_connection(
        db,
        tenant_id=current_user.tenant_id,
        created_by=current_user.id,
        name=payload.name,
        database_type=payload.database_type,
        host=payload.host,
        port=payload.port,
        database_name=payload.database_name,
        username=payload.username,
        password=payload.password,
        ssl_enabled=payload.ssl_enabled,
        connection_options=payload.connection_options,
    )
    record_audit_event(
        db,
        action=AUDIT_CONNECTION_CREATED,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        resource_type="database_connection",
        resource_id=connection.id,
        ip_address=_client_ip(request),
        request_id=getattr(request.state, "request_id", None),
        details={"database_type": connection.database_type, "name": connection.name},
    )
    return DatabaseConnectionResponse.model_validate(connection)


@router.get("/{connection_id}", response_model=DatabaseConnectionResponse)
def get_connection(
    connection_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> DatabaseConnectionResponse:
    connection = _get_owned_connection(db, current_user, connection_id)
    return DatabaseConnectionResponse.model_validate(connection)


@router.put("/{connection_id}", response_model=DatabaseConnectionResponse)
def update_connection(
    connection_id: uuid.UUID,
    payload: DatabaseConnectionUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_tenant_admin()),
) -> DatabaseConnectionResponse:
    connection = _get_owned_connection(db, current_user, connection_id)
    updated = connection_service.update_connection(
        db,
        connection,
        name=payload.name,
        host=payload.host,
        port=payload.port,
        database_name=payload.database_name,
        username=payload.username,
        password=payload.password,
        ssl_enabled=payload.ssl_enabled,
        connection_options=payload.connection_options,
    )
    record_audit_event(
        db,
        action=AUDIT_CONNECTION_UPDATED,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        resource_type="database_connection",
        resource_id=connection.id,
        ip_address=_client_ip(request),
        request_id=getattr(request.state, "request_id", None),
    )
    return DatabaseConnectionResponse.model_validate(updated)


@router.delete("/{connection_id}", status_code=204)
def delete_connection(
    connection_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_tenant_admin()),
) -> None:
    connection = _get_owned_connection(db, current_user, connection_id)
    record_audit_event(
        db,
        action=AUDIT_CONNECTION_DELETED,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        resource_type="database_connection",
        resource_id=connection.id,
        ip_address=_client_ip(request),
        request_id=getattr(request.state, "request_id", None),
    )
    database_connection_repository.delete(db, connection)


@router.post("/{connection_id}/test", response_model=ConnectionTestResponse)
def test_connection(
    connection_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_tenant_admin()),
) -> ConnectionTestResponse:
    connection = _get_owned_connection(db, current_user, connection_id)
    result = connection_tester.test_connection(
        db,
        connection,
        user_id=current_user.id,
        ip_address=_client_ip(request),
        request_id=getattr(request.state, "request_id", None),
    )
    return ConnectionTestResponse(ok=result.ok, message=result.message)


@router.post("/{connection_id}/sync-schema", status_code=202)
def sync_schema(
    connection_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_tenant_admin()),
) -> dict:
    connection = _get_owned_connection(db, current_user, connection_id)
    schema_discovery.sync_schema(
        db,
        connection,
        user_id=current_user.id,
        ip_address=_client_ip(request),
        request_id=getattr(request.state, "request_id", None),
    )
    db.refresh(connection)
    return {"schema_sync_status": connection.schema_sync_status}


@router.get("/{connection_id}/schemas", response_model=list[DatabaseSchemaResponse])
def list_schemas(
    connection_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[DatabaseSchemaResponse]:
    _get_owned_connection(db, current_user, connection_id)
    schemas = database_schema_repository.list_schemas(db, current_user.tenant_id, connection_id)
    return [DatabaseSchemaResponse.model_validate(s) for s in schemas]


@router.get("/{connection_id}/tables", response_model=list[DatabaseTableResponse])
def list_tables(
    connection_id: uuid.UUID,
    schema_name: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[DatabaseTableResponse]:
    _get_owned_connection(db, current_user, connection_id)
    tables = database_schema_repository.list_tables(
        db, current_user.tenant_id, connection_id, schema_name=schema_name
    )
    return [DatabaseTableResponse.model_validate(t) for t in tables]
