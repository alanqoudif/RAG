from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.permissions import require_tenant_admin
from app.core.security import hash_password
from app.core.tenant_context import CurrentUser
from app.dependencies import get_current_user, get_db
from app.exceptions import ConflictError
from app.repositories import role_repository, user_repository
from app.schemas.user import UserCreateRequest, UserResponse

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserResponse])
def list_users(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[UserResponse]:
    users = user_repository.list_by_tenant(db, current_user.tenant_id)
    return [UserResponse.model_validate(u) for u in users]


@router.post("", response_model=UserResponse, status_code=201)
def create_user(
    payload: UserCreateRequest,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_tenant_admin()),
) -> UserResponse:
    if user_repository.get_by_email(db, current_user.tenant_id, payload.email) is not None:
        raise ConflictError("A user with this email already exists in this tenant.")

    user = user_repository.create(
        db,
        tenant_id=current_user.tenant_id,
        email=payload.email,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name,
        is_tenant_admin=payload.is_tenant_admin,
    )
    for role_name in payload.role_names:
        role = role_repository.get_by_name(db, current_user.tenant_id, role_name)
        if role is not None:
            user_repository.assign_role(db, user_id=user.id, role_id=role.id)
    return UserResponse.model_validate(user)
