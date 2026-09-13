"""Smart BethG application controller.

The controller is the application orchestration boundary used by the API.
It deliberately does not execute arbitrary tools directly. Requests are
recorded as queued tasks and tool capabilities are exposed as metadata;
execution must go through the security/approval/execution layers.
"""

from services.task_service import TaskService


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

    def __init__(self, task_service=None, tool_orchestrator=None):
        self.task_service = task_service or TaskService()
        self.tool_orchestrator = tool_orchestrator or ToolOrchestrator()

    def handle_request(self, request, user_id, workspace="default"):
        if not isinstance(request, str) or not request.strip():
            raise ValueError("Request must be a non-empty string.")
        if not isinstance(workspace, str) or not workspace.strip():
            raise ValueError("Workspace must be a non-empty string.")

        return self.task_service.create(
            user_id=user_id,
            request=request.strip(),
            workspace=workspace.strip(),
        )
