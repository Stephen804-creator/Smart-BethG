"""Registry of trusted background job handlers.

The API surfaces and business services stay in the web app. The worker boundary is
responsible for executing long-running jobs that should not block HTTP requests.
"""

from __future__ import annotations

from typing import Callable, Dict

from services.mission_executor import MissionExecutor
from services.specialist_coordinator import SpecialistCoordinator
from services.workflow_executor import WorkflowExecutor


def default_job_handlers() -> Dict[str, Callable]:
    """Return the default, trusted job handlers for asynchronous work."""
    mission_executor = MissionExecutor()
    workflow_executor = WorkflowExecutor()
    specialist_coordinator = SpecialistCoordinator()
    return {
        "mission.execute": mission_executor.execute,
        "workflow.execute": workflow_executor.execute,
        "agent.team.execute": specialist_coordinator.execute,
    }
