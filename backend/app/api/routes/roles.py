import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.permissions import require_tenant_admin
from app.core.tenant_context import CurrentUser
from app.dependencies import get_current_user, get_db
from app.exceptions import ConflictError, NotFoundError
from app.repositories import role_repository, user_repository
from app.schemas.role import AssignRoleRequest, RoleCreateRequest, RoleResponse

router = APIRouter(prefix="/roles", tags=["roles"])


@router.get("", response_model=list[RoleResponse])
def list_roles(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[RoleResponse]:
    roles = role_repository.list_by_tenant(db, current_user.tenant_id)
    return [RoleResponse.model_validate(r) for r in roles]


@router.post("", response_model=RoleResponse, status_code=201)
def create_role(
    payload: RoleCreateRequest,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_tenant_admin()),
) -> RoleResponse:
    if role_repository.get_by_name(db, current_user.tenant_id, payload.name) is not None:
        raise ConflictError("A role with this name already exists in this tenant.")
    role = role_repository.create(
        db, tenant_id=current_user.tenant_id, name=payload.name, description=payload.description
    )
    return RoleResponse.model_validate(role)


@router.post("/users/{user_id}/assign", status_code=204)
def assign_role_to_user(
    user_id: str,
    payload: AssignRoleRequest,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_tenant_admin()),
) -> None:
    target_user = user_repository.get_by_id(db, current_user.tenant_id, uuid.UUID(user_id))
    if target_user is None:
        raise NotFoundError("User not found.")
    role = role_repository.get_by_id(db, current_user.tenant_id, payload.role_id)
    if role is None:
        raise NotFoundError("Role not found.")
    user_repository.assign_role(db, user_id=target_user.id, role_id=role.id)
