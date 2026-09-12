"""Smart BethG application-facing authorization boundary."""
from dataclasses import dataclass
from .policy_engine import PolicyEngine
from .security_context import SecurityContext

@dataclass(frozen=True)
class AccessRequest:
    request_id: str
    action: str
    permission: str
    resource: str

class AccessControl:
    def __init__(self, policy_engine=None):
        self.policy_engine = policy_engine or PolicyEngine()

    def authorize(self, context: SecurityContext, request: AccessRequest):
        return self.policy_engine.evaluate(
            context, request.action, request.permission
        )
