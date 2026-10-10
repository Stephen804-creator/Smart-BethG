"""Typed approval record with decoded payload/result fields."""
import json
from dataclasses import asdict, dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class Approval:
    id: str
    user_id: int
    action: str
    resource: str
    status: str
    execution_status: str = "pending"
    payload: dict | None = None
    expires_at: str | None = None
    decided_at: str | None = None
    executed_at: str | None = None
    execution_result: Any = None
    created_at: str | None = None

    @classmethod
    def from_record(cls, record: Mapping[str, Any]):
        payload = record.get("payload")
        if payload is None and record.get("payload_json"):
            try:
                payload = json.loads(record["payload_json"])
            except (TypeError, json.JSONDecodeError):
                payload = None
        result = record.get("execution_result")
        if isinstance(result, str):
            try:
                result = json.loads(result)
            except (TypeError, json.JSONDecodeError):
                pass
        return cls(
            id=record["id"], user_id=record["user_id"], action=record["action"],
            resource=record["resource"], status=record["status"],
            execution_status=record.get("execution_status") or "pending",
            payload=payload, expires_at=record.get("expires_at"),
            decided_at=record.get("decided_at"), executed_at=record.get("executed_at"),
            execution_result=result, created_at=record.get("created_at"),
        )

    def to_dict(self):
        return asdict(self)
