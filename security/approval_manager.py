"""Smart BethG approval gate.

LV: Approval is tied to one request, user, action and resource. It is not a
global switch that makes an agent trusted forever.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

@dataclass(frozen=True)
class ApprovalRequest:
    approval_id: str
    request_id: str
    user_id: str
    action: str
    resource: str
    created_at: str

class ApprovalManager:
    def __init__(self):
        self._requests = {}
        self._decisions = {}

    def create_request(self, request_id, user_id, action, resource):
        item = ApprovalRequest(
            str(uuid4()), request_id, user_id, action, resource,
            datetime.now(timezone.utc).isoformat()
        )
        self._requests[item.approval_id] = item
        return item

    def decide(self, approval_id, approved):
        if approval_id not in self._requests:
            raise KeyError("Unknown approval request.")
        self._decisions[approval_id] = bool(approved)

    def is_approved(self, approval_id):
        return self._decisions.get(approval_id, False)
