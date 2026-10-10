"""Smart BethG application controller.

The controller is the application orchestration boundary used by the API.

Previously this only ever recorded a "queued" task row and stopped -
nothing downstream ever read or acted on it. Every request sat in the
tasks table forever, no matter what it asked for. Now it also runs the
request through the real agent loop (agent/executor.py), which
classifies intent, builds a (single-step) plan, and either replies via
chat or executes a real tool through the full
permission/risk/approval/verification pipeline. The task row is kept
for history, and its status is updated to reflect what actually
happened - not left as "queued" forever.
"""

from services.task_service import TaskService
from logging_setup import get_logger

logger = get_logger("task")
from agent.executor import AgentExecutor
from agent.request import AgentRequest


class ToolOrchestrator:
    """Registry of controlled tool capabilities exposed by Smart BethG."""

    def __init__(self):
        self._tools = [
            {
                "name": "filesystem.read",
                "description": "Read files inside an assigned workspace.",
                "permission": "filesystem.read",
                "risk": "low",
            },
            {
                "name": "filesystem.write",
                "description": "Write files inside an assigned workspace.",
                "permission": "filesystem.write",
                "risk": "medium",
            },
            {
                "name": "terminal.execute",
                "description": "Execute an explicitly allowed program through the controlled runner.",
                "permission": "terminal.execute",
                "risk": "high",
            },
            {
                "name": "git.read",
                "description": "Read Git repository state.",
                "permission": "git.read",
                "risk": "low",
            },
            {
                "name": "git.write",
                "description": "Perform approved Git write operations.",
                "permission": "git.write",
                "risk": "high",
            },
            {
                "name": "network.request",
                "description": "Make an approved outbound network request.",
                "permission": "network.request",
                "risk": "high",
            },
            {
                "name": "docker.run",
                "description": "Run an approved Docker operation.",
                "permission": "docker.run",
                "risk": "high",
            },
        ]

    def list_tools(self):
        return list(self._tools)


class Controller:
    """Coordinate API requests without bypassing security controls."""

    def __init__(self, task_service=None, tool_orchestrator=None, agent_executor=None):
        self.task_service = task_service or TaskService()
        self.tool_orchestrator = tool_orchestrator or ToolOrchestrator()
        self.agent_executor = agent_executor or AgentExecutor()

    def handle_request(self, request, user, workspace="default"):
        """
        `user` is the full authenticated user dict (must include "id",
        should include "role" - see security/role_permissions.py for
        what happens when it's missing: fails closed to the least-
        privileged role, not open).
        """
        if not isinstance(request, str) or not request.strip():
            raise ValueError("Request must be a non-empty string.")
        if not isinstance(workspace, str) or not workspace.strip():
            raise ValueError("Workspace must be a non-empty string.")

        task = self.task_service.create(
            user_id=user["id"],
            request=request.strip(),
            workspace=workspace.strip(),
        )

        try:
            agent_request = AgentRequest(text=request.strip(), user=user, workspace=workspace.strip())
            outcome = self.agent_executor.run(agent_request)
        except Exception:
            logger.exception("Task execution failed: task_id=%s user_id=%s", task["task_id"], user["id"])
            self.task_service.update_status(task["task_id"], "failed")
            return {**task, "status": "failed", "error": "The task failed unexpectedly. Please try again later."}

        self.task_service.update_status(task["task_id"], outcome["status"])
        return {**task, **outcome}
