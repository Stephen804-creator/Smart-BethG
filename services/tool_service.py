"""
Smart BethG - Tool Service (T0601 wiring + T0602 + T0603 lifecycle)

This is the piece that was missing: the security stack (SecurityContext,
PolicyEngine, RiskEngine, ExecutionEngine) and the tool implementations
(FileReader, FileWriter, GitTool, CommandRunner, NetworkTool, DockerTool)
already existed as real code, but nothing called them - a request never
reached this far no matter what a user asked for. This connects them.

Flow for every call: build a SecurityContext for the user (role ->
permissions) -> ask ExecutionEngine to authorize -> on "deny", stop and
say why -> on "approval_required", persist a real approval via
ApprovalService and stop -> on "allow", call the real tool -> verify the
result honestly (agent/result_verifier.py) rather than assuming success.

Every decision (deny / approval_required / executed) is also recorded
via AuditService into the `audit_events` table - previously nothing
wrote to that table at all, despite it existing in the schema and
having a route (GET /audit) that could only ever return an empty list.

All 7 registered tools (controller.ToolOrchestrator) are wired:
filesystem.read/write, git.read/write, terminal.execute, network.request,
docker.run.
"""
import os
import uuid

import config
from execution.execution_engine import ExecutionEngine, ExecutionPermit
from security.access_control import AccessRequest
from security.role_permissions import build_security_context
from services.approval_service import ApprovalService
from services.audit_service import AuditService
from agent.result_verifier import verify_result
from filesystem.file_reader import FileReader
from filesystem.file_writer import FileWriter
from git.git_tool import GitTool
from execution.command_runner import CommandRunner
from network.network_tool import NetworkTool
from docker.docker_tool import DockerTool
from logging_setup import get_logger

logger = get_logger("task")


def resolve_workspace_root(user_id, workspace_name: str) -> str:
    """
    Maps a workspace to a directory owned by one authenticated user.
    The user ID comes from the server-side session, never the request
    body. Workspace names are sanitized and never treated as paths.
    """
    safe_name = "".join(c for c in (workspace_name or "") if c.isalnum() or c in ("-", "_")) or "default"
    user_root = os.path.join(config.STORAGE_DIRS["projects"], str(user_id))
    root = os.path.join(user_root, safe_name)
    os.makedirs(root, exist_ok=True)
    return root


class ToolService:
    def __init__(self, execution_engine=None, approval_service=None, audit_service=None):
        self.engine = execution_engine or ExecutionEngine()
        self.approvals = approval_service or ApprovalService()
        self.audit = audit_service or AuditService()
        self._file_reader = FileReader()
        self._file_writer = FileWriter()
        self._git_tool = GitTool()
        self._command_runner = CommandRunner()
        self._network_tool = NetworkTool()
        self._docker_tool = DockerTool()

    def execute(self, user: dict, action: str, workspace: str = "default", **kwargs) -> dict:
        workspace_root = resolve_workspace_root(user["id"], workspace)
        resource = f"workspace:{workspace}"

        context = build_security_context(user, workspace=workspace_root)
        request_id = str(uuid.uuid4())
        access_request = AccessRequest(
            request_id=request_id, action=action, permission=action, resource=resource
        )

        decision, permit = self.engine.authorize(context, access_request)

        if decision.decision == "deny":
            logger.info("Tool denied: action=%s user=%s reason=%s", action, user["id"], decision.reason)
            self.audit.record(user["id"], action, resource, "deny", details=decision.reason)
            return {"success": False, "status": "denied", "reason": decision.reason}

        if decision.decision == "approval_required":
            approval = self.approvals.create(
                user["id"], action, resource,
                payload={"workspace": workspace, "kwargs": kwargs, "request_id": request_id},
            )
            logger.info(
                "Tool requires approval: action=%s user=%s approval_id=%s",
                action, user["id"], approval["id"],
            )
            self.audit.record(
                user["id"], action, resource, "approval_required",
                risk_level=decision.risk.value,
                details=f"approval_id={approval['id']}",
            )
            return {
                "success": False,
                "status": "approval_required",
                "approval_id": approval["id"],
                "reason": decision.reason,
            }

        tool_fn = self._resolve_tool(action)
        if tool_fn is None:
            return {"success": False, "status": "unknown_tool", "reason": f"No tool registered for action {action!r}."}

        try:
            raw_result = tool_fn(permit, workspace_root, **kwargs)
        except Exception as exc:
            logger.exception(
                "Tool execution raised: action=%s user=%s error_type=%s",
                action, user["id"], type(exc).__name__,
            )
            self.audit.record(
                user["id"], action, resource, "failed", details=type(exc).__name__
            )
            return {
                "success": False,
                "status": "failed",
                "reason": "Tool execution failed. Check the task result or server logs.",
            }

        verified = verify_result(action, raw_result)
        if "operation" in kwargs:
            # Lets callers (e.g. the executor rendering a summary) know
            # which git/filesystem sub-operation this was, since the
            # action name alone ("git.read") doesn't distinguish
            # status/diff/branches.
            verified["operation"] = kwargs["operation"]
        logger.info(
            "Tool executed: action=%s user=%s success=%s status=%s",
            action, user["id"], verified["success"], verified["status"],
        )
        self.audit.record(
            user["id"], action, resource,
            "allow" if verified["success"] else "allow_but_failed",
            risk_level=permit.risk_level if permit else None,
            details=verified.get("status"),
        )
        return verified

    def execute_approved(self, user: dict, approval_id: str) -> dict:
        """
        Resume the exact saved operation after an owner approves it.
        The approval is claimed atomically before any side effect. If a process
        crashes while a tool is running, the record stays 'running' and is not
        blindly replayed; an operator must reconcile the outcome.
        """
        from fastapi import HTTPException, status

        record = self.approvals.get_for_user(approval_id, user["id"])
        if not record:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Approval not found.")
        if record.get("status") != "approved":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Approval has not been approved.")

        payload = record.get("payload") or {}
        workspace = payload.get("workspace")
        kwargs = payload.get("kwargs")
        request_id = payload.get("request_id") or str(uuid.uuid4())
        if not isinstance(workspace, str) or not workspace.strip() or not isinstance(kwargs, dict):
            raise HTTPException(status_code=422, detail="Saved operation payload is missing or invalid.")
        if record.get("resource") != f"workspace:{workspace}":
            raise HTTPException(status_code=409, detail="Saved operation resource does not match its approval.")
        action = record.get("action")
        tool_fn = self._resolve_tool(action)
        if tool_fn is None:
            raise HTTPException(status_code=422, detail="The approved tool is no longer registered.")

        # Claim before execution. A concurrent or replayed request cannot run
        # the same approved operation a second time.
        self.approvals.claim_for_execution(approval_id, user["id"])
        workspace_root = resolve_workspace_root(user["id"], workspace)
        context = build_security_context(user, workspace=workspace_root)
        access_request = AccessRequest(
            request_id=request_id, action=action, permission=action,
            resource=record["resource"],
        )
        decision, permit = self.engine.authorize(context, access_request)

        if decision.decision == "deny":
            result = {"success": False, "status": "denied", "reason": decision.reason}
            self.approvals.mark_execution_result(approval_id, user["id"], "failed", result)
            self.audit.record(
                user["id"], action, record["resource"], "approved_but_denied",
                risk_level=decision.risk.value, details=f"approval_id={approval_id}; {decision.reason}",
            )
            return {**result, "approval_id": approval_id, "execution_status": "failed"}

        # PolicyEngine returns no permit for high-risk actions even after the
        # explicit approval. Re-issue a narrow permit only for this saved,
        # owner-bound action after current authorization has been checked.
        if decision.decision == "approval_required":
            permit = ExecutionPermit(
                request_id=request_id, action=action,
                resource=record["resource"], risk_level=decision.risk.value,
            )
        if permit is None:
            result = {"success": False, "status": "denied", "reason": "No execution permit was issued."}
            self.approvals.mark_execution_result(approval_id, user["id"], "failed", result)
            return {**result, "approval_id": approval_id, "execution_status": "failed"}

        try:
            raw_result = tool_fn(permit, workspace_root, **kwargs)
            verified = verify_result(action, raw_result)
            if "operation" in kwargs:
                verified["operation"] = kwargs["operation"]
            execution_status = "completed" if verified.get("success") else "failed"
        except Exception as exc:
            # A tool may have performed a partial external side effect before
            # raising. Never auto-retry an operation whose outcome is unknown.
            logger.exception(
                "Approved tool outcome is indeterminate: approval_id=%s action=%s user=%s",
                approval_id, action, user["id"],
            )
            verified = {
                "success": False, "status": "indeterminate",
                "reason": "The operation raised an error. Its side effects must be checked before retrying.",
            }
            execution_status = "indeterminate"

        self.approvals.mark_execution_result(approval_id, user["id"], execution_status, verified)
        self.audit.record(
            user["id"], action, record["resource"],
            "approved_executed" if execution_status == "completed" else "approved_execution_" + execution_status,
            risk_level=decision.risk.value,
            details=f"approval_id={approval_id}; status={verified.get('status')}",
        )
        return {
            "success": bool(verified.get("success")),
            "status": verified.get("status", execution_status),
            "approval_id": approval_id,
            "execution_status": execution_status,
            "result": verified,
        }

    def _resolve_tool(self, action):
        return {
            "filesystem.read": self._run_filesystem_read,
            "filesystem.write": self._run_filesystem_write,
            "git.read": self._run_git_read,
            "git.write": self._run_git_write,
            "terminal.execute": self._run_terminal_execute,
            "network.request": self._run_network_request,
            "docker.run": self._run_docker_run,
        }.get(action)

    def _run_filesystem_read(self, permit, workspace_root, path=None, **_):
        if not path:
            raise ValueError("filesystem.read requires a 'path'.")
        content = self._file_reader.read(path, workspace_root)
        return {"content": content, "path": path}

    def _run_filesystem_write(self, permit, workspace_root, path=None, content="", **_):
        if not path:
            raise ValueError("filesystem.write requires a 'path'.")
        written_path = self._file_writer.write(path, content, workspace_root)
        return {"path": written_path}

    def _run_git_read(self, permit, workspace_root, operation="status", **_):
        if operation == "diff":
            return self._git_tool.diff(permit, cwd=workspace_root)
        if operation == "branches":
            return self._git_tool.branches(permit, cwd=workspace_root)
        return self._git_tool.status(permit, cwd=workspace_root)

    def _run_git_write(self, permit, workspace_root, operation="commit", message=None, branch=None, **_):
        if operation == "checkout":
            if not branch:
                raise ValueError("git.write (checkout) requires a 'branch'.")
            return self._git_tool.checkout(permit, cwd=workspace_root, branch=branch)
        if not message:
            raise ValueError("git.write requires a commit 'message'.")
        return self._git_tool.commit(permit, cwd=workspace_root, message=message)

    def _run_terminal_execute(self, permit, workspace_root, program=None, args=None, timeout=30, **_):
        if not program:
            raise ValueError("terminal.execute requires a 'program'.")
        return self._command_runner.run(permit, program, args or [], cwd=workspace_root, timeout=timeout)

    def _run_network_request(self, permit, workspace_root, url=None, timeout=15, **_):
        if not url:
            raise ValueError("network.request requires a 'url'.")
        content = self._network_tool.get(permit, url, timeout=timeout)
        return {"content": content, "url": url}

    def _run_docker_run(self, permit, workspace_root, args=None, **_):
        completed = self._docker_tool.run(permit, args or [], cwd=workspace_root)
        return {
            "return_code": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        }
