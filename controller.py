"""Smart BethG application controller.

The controller is the application orchestration boundary used by the API.

The controller runs requests through the agent loop (agent/executor.py),
which classifies intent and builds a plan. Chat, memory, and configured
research can run through their supported services. Direct host-side tools
are disabled; tool intents fail closed until a real application connector,
scoped authorization, and connector-aware approvals are implemented.
Task history records the actual outcome instead of leaving requests queued.
"""

from services.task_service import TaskService
from logging_setup import get_logger

logger = get_logger("task")
from agent.executor import AgentExecutor
from agent.request import AgentRequest


class ToolOrchestrator:
    """Registry of controlled tool capabilities exposed by Smart BethG."""

    def __init__(self):
        # Direct server-side tools are intentionally disabled.
        # Capabilities will be exposed only through explicit application connectors
        # with scoped permissions and per-action approval.
        self._tools = []

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
            self.task_service.update_status(user["id"], task["task_id"], "failed")
            return {**task, "status": "failed", "error": "The task failed unexpectedly. Please try again later."}

        self.task_service.update_status(user["id"], task["task_id"], outcome["status"])
        return {**task, **outcome}
