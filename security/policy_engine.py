"""Smart BethG policy decision point.

LV: The model proposes. This layer decides. Unknown or explicitly dangerous
operations fail closed. High/critical operations require human approval.
"""
from dataclasses import dataclass
from .permission_manager import PermissionManager
from .risk_engine import RiskEngine, RiskLevel
from .security_context import SecurityContext

@dataclass(frozen=True)
class PolicyDecision:
    decision: str
    action: str
    permission: str
    risk: RiskLevel
    reason: str

class PolicyEngine:
    DENIED_ACTIONS = {
        "credential.access",
        "security_control.change",
        "host.kernel.change",
        "sandbox.escape",
    }
    APPROVAL_RISKS = {RiskLevel.HIGH, RiskLevel.CRITICAL}

    def __init__(self, permission_manager=None, risk_engine=None):
        self.permission_manager = permission_manager or PermissionManager()
        self.risk_engine = risk_engine or RiskEngine()

    def evaluate(self, context: SecurityContext, action: str, permission: str):
        risk = self.risk_engine.classify(action)
        if action in self.DENIED_ACTIONS:
            return PolicyDecision("deny", action, permission, risk,
                                  "Action explicitly denied by policy.")
        result = self.permission_manager.check(context, permission)
        if not result.granted:
            return PolicyDecision("deny", action, permission, risk, result.reason)
        if risk in self.APPROVAL_RISKS:
            return PolicyDecision("approval_required", action, permission, risk,
                                  "Explicit human approval is required.")
        return PolicyDecision("allow", action, permission, risk,
                              "Action satisfies current policy.")
