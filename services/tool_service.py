"""Connector-first capability boundary.

Direct filesystem, Git, terminal, network and Docker execution on the application
host is disabled. Keep approvals/auditing as reusable primitives for future
application connectors; do not re-enable host execution as a shortcut.
"""
import os

from fastapi import HTTPException, status

import config
from services.approval_service import ApprovalService
from services.audit_service import AuditService
from logging_setup import get_logger

logger = get_logger("task")
DIRECT_EXECUTION_DISABLED_REASON = (
    "Direct server-side tool execution is disabled. Connect an application "
    "connector and grant only the required permissions before performing actions."
)


def normalize_workspace_name(workspace_name: str) -> str:
    """Return a safe canonical label; never interpret it as a filesystem path."""
    return "".join(
        c for c in (workspace_name or "")
        if c.isalnum() or c in ("-", "_")
    ) or "default"


def resolve_workspace_root(user_id, workspace_name: str) -> str:
    """Return a per-user workspace path for legacy references; no tools execute here."""
    safe_name = normalize_workspace_name(workspace_name)
    user_root = os.path.join(config.STORAGE_DIRS["projects"], str(user_id))
    return os.path.join(user_root, safe_name)


class ToolService:
    """Fail-closed compatibility boundary until connector execution is implemented."""

    def __init__(self, execution_engine=None, approval_service=None, audit_service=None):
        self.approvals = approval_service or ApprovalService()
        self.audit = audit_service or AuditService()

    def execute(self, user: dict, action: str, workspace: str = "default", **kwargs) -> dict:
        user_id = user.get("id") if isinstance(user, dict) else None
        workspace = normalize_workspace_name(workspace)
        resource = f"workspace:{workspace}"
        if user_id is not None and callable(getattr(self.audit, "record", None)):
            try:
                self.audit.record(
                    user_id, action, resource, "blocked",
                    details="Direct host execution disabled; connector required.",
                )
            except Exception:
                logger.exception("Could not persist blocked-tool audit event")
        logger.info("Blocked direct server-side tool action=%s user=%s", action, user_id)
        return {
            "success": False,
            "status": "unavailable",
            "reason": DIRECT_EXECUTION_DISABLED_REASON,
            "connector_required": True,
        }

    def execute_approved(self, user: dict, approval_id: str) -> dict:
        """Never execute legacy host-tool approvals; connector approvals need a separate executor."""
        record = self.approvals.get_for_user(approval_id, user["id"])
        if not record:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Approval not found.")
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail=(
                "This approval targets a disabled direct server-side tool. "
                "No host operation was executed; use an application connector instead."
            ),
        )
