"""Fail-closed connector policy decisions."""
from dataclasses import dataclass

@dataclass(frozen=True)
class PolicyDecision:
    decision: str
    reason: str
    requires_approval: bool
    risk: str

class PolicyEngine:
    def evaluate(self, capability, installation, user_id):
        if capability is None:
            return PolicyDecision("deny","Action is not registered.",False,"unknown")
        if not installation or installation.get("user_id")!=user_id:
            return PolicyDecision("deny","Connector installation not found for this user.",False,capability.risk)
        if installation.get("status")!="connected" and installation.get("connector_key")!="smartbethg":
            return PolicyDecision("deny","Connector is not connected.",False,capability.risk)
        if capability.permission not in set(installation.get("granted_permissions") or []):
            return PolicyDecision("deny","Connector permission has not been granted.",False,capability.risk)
        if capability.side_effecting or capability.risk in {"write","destructive","financial"}:
            return PolicyDecision("approval_required","This action can change external state.",True,capability.risk)
        return PolicyDecision("allow","Read-only action is permitted.",False,capability.risk)
