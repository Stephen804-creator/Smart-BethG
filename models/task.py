"""Typed task record."""
from dataclasses import asdict, dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class Task:
    id: int
    user_id: int
    request: str
    status: str
    workspace: str
    created_at: str | None = None

    @classmethod
    def from_record(cls, record: Mapping[str, Any]):
        return cls(
            id=record["id"], user_id=record["user_id"], request=record["request"],
            status=record["status"], workspace=record["workspace"],
            created_at=record.get("created_at"),
        )

    def to_dict(self):
        return asdict(self)
