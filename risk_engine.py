"""Smart BethG risk classification.

LV: Unknown actions fail closed and receive HIGH risk.
"""
from enum import Enum

class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class RiskEngine:
    LEVELS = {
        "filesystem.read": RiskLevel.LOW,
        "filesystem.write": RiskLevel.MEDIUM,
        "terminal.execute": RiskLevel.HIGH,
        "git.read": RiskLevel.LOW,
        "git.write": RiskLevel.HIGH,
        "docker.run": RiskLevel.HIGH,
        "network.request": RiskLevel.HIGH,
        "credential.access": RiskLevel.CRITICAL,
        "security_control.change": RiskLevel.CRITICAL,
    }

    def classify(self, action: str) -> RiskLevel:
        return self.LEVELS.get(action, RiskLevel.HIGH)
