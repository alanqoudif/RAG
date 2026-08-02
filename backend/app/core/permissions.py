"""Role-based access control helpers. Table/column/row-level data permissions are handled
separately in app.services.database.permission_service (Phase 4) — this module only covers
coarse-grained, role-based endpoint authorization.
"""

from collections.abc import Callable

from fastapi import Depends

from app.core.tenant_context import CurrentUser
from app.exceptions import ForbiddenError


def require_role(*allowed_roles: str) -> Callable[..., CurrentUser]:
    from app.dependencies import get_current_user

    def _dependency(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if current_user.is_tenant_admin or any(current_user.has_role(r) for r in allowed_roles):
            return current_user
        raise ForbiddenError("You do not have permission to perform this action.")

    return _dependency


def require_tenant_admin() -> Callable[..., CurrentUser]:
    from app.dependencies import get_current_user

    def _dependency(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if not current_user.is_tenant_admin:
            raise ForbiddenError("This action requires tenant administrator privileges.")
        return current_user

    return _dependency
