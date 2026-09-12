"""Smart BethG structured audit events."""
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any
import json

@dataclass(frozen=True)
class AuditEvent:
    event_type: str
    request_id: str
    user_id: str
    agent_id: str
    action: str
    resource: str
    decision: str
    risk_level: str
    details: dict[str, Any]
    timestamp: str

    @classmethod
    def create(cls, **kwargs):
        return cls(
            timestamp=datetime.now(timezone.utc).isoformat(),
            details=kwargs.pop("details", {}) or {},
            **kwargs,
        )

    def to_json(self):
        return json.dumps(asdict(self), separators=(",", ":"))
