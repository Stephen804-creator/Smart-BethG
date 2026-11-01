"""Registry of trusted background job handlers.

The API surfaces and business services stay in the web app. The worker boundary is
responsible for executing long-running jobs that should not block HTTP requests.
"""

from __future__ import annotations

from typing import Callable, Dict

from services.file_service import FileService
from services.knowledge_service import KnowledgeService
from services.mission_executor import MissionExecutor
from services.specialist_coordinator import SpecialistCoordinator
from services.workflow_executor import WorkflowExecutor


def default_job_handlers() -> Dict[str, Callable]:
    """Return the default, trusted job handlers for asynchronous work."""
    mission_executor = MissionExecutor()
    workflow_executor = WorkflowExecutor()
    specialist_coordinator = SpecialistCoordinator()
    file_service = FileService()
    knowledge_service = KnowledgeService(file_service=file_service)

    def handle_file_extract(job):
        payload = job["payload"]
        return file_service.extract_text(payload["user_id"], payload["file_id"])

    def handle_knowledge_ingest(job):
        payload = job["payload"]
        return knowledge_service.ingest_file(
            payload["user_id"],
            payload["file_id"],
            payload.get("workspace", "default"),
        )

    return {
        "mission.execute": mission_executor.execute,
        "workflow.execute": workflow_executor.execute,
        "agent.team.execute": specialist_coordinator.execute,
        "file.extract": handle_file_extract,
        "knowledge.ingest": handle_knowledge_ingest,
    }
