"""Typed audit-event record."""
from dataclasses import asdict, dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class AuditEventRecord:
    id: int | None
    user_id: int | None
    action: str | None
    resource: str | None
    decision: str | None
    risk_level: str | None = None
    details: str | None = None
    agent_id: str | None = None
    created_at: str | None = None

    @classmethod
    def from_record(cls, record: Mapping[str, Any]):
        return cls(
            id=record.get("id"), user_id=record.get("user_id"),
            action=record.get("action"), resource=record.get("resource"),
            decision=record.get("decision"), risk_level=record.get("risk_level"),
            details=record.get("details"), agent_id=record.get("agent_id"),
            created_at=record.get("created_at"),
        )

    def to_dict(self):
        return asdict(self)
