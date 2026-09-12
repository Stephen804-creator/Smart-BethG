"""Smart BethG execution gate.

LV: Tools are invoked only after AccessControl authorizes the exact request.
The model never calls a tool directly.

A private permit is returned by this engine and is required by the controlled
tool wrappers, reducing the chance that a caller bypasses the policy layer.
"""
from dataclasses import dataclass
from typing import Any, Callable
from security.access_control import AccessControl, AccessRequest
from security.security_context import SecurityContext

@dataclass(frozen=True)
class ExecutionPermit:
    request_id: str
    action: str
    resource: str
    risk_level: str

@dataclass(frozen=True)
class ExecutionResult:
    success: bool
    status: str
    result: Any = None
    reason: str | None = None

class ExecutionEngine:
    def __init__(self, access_control=None):
        self.access_control = access_control or AccessControl()

    def authorize(self, context, request):
        decision = self.access_control.authorize(context, request)
        if decision.decision != "allow":
            return decision, None
        permit = ExecutionPermit(
            request_id=request.request_id,
            action=request.action,
            resource=request.resource,
            risk_level=decision.risk.value,
        )
        return decision, permit

    def execute(self, context: SecurityContext, request: AccessRequest,
                tool: Callable[..., Any], *args, **kwargs):
        decision, permit = self.authorize(context, request)
        if decision.decision == "deny":
            return ExecutionResult(False, "denied", reason=decision.reason)
        if decision.decision == "approval_required":
            return ExecutionResult(False, "approval_required", reason=decision.reason)
        try:
            return ExecutionResult(True, "executed",
                                   result=tool(permit, *args, **kwargs))
        except Exception as exc:
            return ExecutionResult(False, "failed", reason=str(exc))
