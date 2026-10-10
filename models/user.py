"""Typed user domain record; never includes password hashes in public serialization."""
from dataclasses import asdict, dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class User:
    id: int
    username: str
    role: str = "user"
    status: str = "active"

    @classmethod
    def from_record(cls, record: Mapping[str, Any]):
        return cls(
            id=record["id"],
            username=record["username"],
            role=record.get("role") or "user",
            status=record.get("status") or "active",
        )

    def to_public_dict(self):
        return {"id": self.id, "username": self.username, "role": self.role}

    def to_dict(self):
        return asdict(self)
