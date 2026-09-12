"""Smart BethG audit persistence.

LV: Persistence is separated from the logger so JSONL can later be replaced
by a database or centralized immutable log without changing callers.
"""
from pathlib import Path
from .audit_events import AuditEvent

class AuditStore:
    def __init__(self, path="logs/audit.jsonl"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, event: AuditEvent):
        with self.path.open("a", encoding="utf-8") as file:
            file.write(event.to_json() + "\n")
