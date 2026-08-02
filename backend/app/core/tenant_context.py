import uuid
from dataclasses import dataclass


@dataclass(frozen=True)
class CurrentUser:
    id: uuid.UUID
    tenant_id: uuid.UUID
    email: str
    is_tenant_admin: bool
    roles: frozenset[str]

    def has_role(self, role_name: str) -> bool:
        return self.is_tenant_admin or role_name in self.roles
