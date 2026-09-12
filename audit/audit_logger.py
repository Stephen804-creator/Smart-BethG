"""Smart BethG audit logger.

LV: Log requests, policy decisions, approvals, execution outcomes and
denials. Never log passwords, tokens, private keys or other secrets.
"""
from .audit_events import AuditEvent
from .audit_store import AuditStore

class AuditLogger:
    def __init__(self, store=None):
        self.store = store or AuditStore()

    def record(self, **kwargs):
        event = AuditEvent.create(**kwargs)
        self.store.append(event)
        return event
