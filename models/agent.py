"""Typed agent domain record."""
from dataclasses import asdict, dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class Agent:
    id: int
    user_id: int
    name: str
    status: str = "active"

    @classmethod
    def from_record(cls, record: Mapping[str, Any]):
        return cls(record["id"], record["user_id"], record["name"], record.get("status") or "active")

    def to_dict(self):
        return asdict(self)
