"""Smart BethG permission checking.

LV: Permission answers whether a principal possesses a named capability.
It does not decide whether a particular operation is safe; PolicyEngine does.
"""
from dataclasses import dataclass
from .security_context import SecurityContext

@dataclass(frozen=True)
class PermissionResult:
    granted: bool
    reason: str

class PermissionManager:
    def check(self, context: SecurityContext, permission: str) -> PermissionResult:
        if context.has_permission(permission):
            return PermissionResult(True, "Permission is present.")
        return PermissionResult(False, "Permission is not present.")
