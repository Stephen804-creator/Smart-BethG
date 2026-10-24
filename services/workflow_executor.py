"""Durable workflow dispatch. Mission steps only; unsupported adapters fail closed."""
from services.workflow_service import WorkflowService
from services.mission_service import MissionService


class WorkflowExecutor:
    def __init__(self, workflows=None, missions=None):
        self.workflows = workflows or WorkflowService()
        self.missions = missions or MissionService()

    def execute(self, job):
        payload = job.get("payload") or {}
        user_id = job["user_id"]
        workflow_id, run_id = int(payload.get("workflow_id", 0)), int(payload.get("run_id", 0))
        workflow, run = self.workflows.get(user_id, workflow_id), self.workflows.get_run(user_id, run_id)
        if not workflow or not run or run["status"] not in {"queued", "running"}:
            return {"status": "stale_or_missing"}
        if workflow["version"] != int(payload.get("workflow_version", -1)) or run["workflow_version"] != workflow["version"]:
            self.workflows.update_run(user_id, run_id, "failed", error="Workflow version changed after enqueue.", terminal=True)
            return {"status": "failed", "reason": "version_mismatch"}
        steps = workflow.get("steps") or []
        outputs = (run.get("result") or {}).get("outputs", [])
        self.workflows.update_run(user_id, run_id, "running")
        for index, step in enumerate(steps):
            if index < int(run.get("current_step") or 0):
                continue
            if step.get("type") != "mission":
                self.workflows.update_run(user_id, run_id, "failed", current_step=index, result={"outputs": outputs},
                    error=f"No trusted executor is enabled for step type '{step.get('type')}'.", terminal=True)
                return {"status": "failed", "step_index": index}
            cfg = step.get("config") or {}
            objective = str(cfg.get("objective") or "").strip()
            if not objective:
                self.workflows.update_run(user_id, run_id, "failed", current_step=index, result={"outputs": outputs},
                    error=f"Mission step {index + 1} requires config.objective.", terminal=True)
                return {"status": "failed", "step_index": index}
            try:
                mission = self.missions.create(user_id, objective, priority=cfg.get("priority", "normal"),
                                               project_id=cfg.get("project_id"), steps=cfg.get("steps") or [])
                started = self.missions.start_run(user_id, mission["id"])
            except ValueError as exc:
                self.workflows.update_run(user_id, run_id, "failed", current_step=index, result={"outputs": outputs},
                    error=f"Mission step {index + 1}: {exc}", terminal=True)
                return {"status": "failed", "step_index": index}
            outputs.append({"step_id": step.get("id"), "type": "mission", "mission_id": mission["id"],
                            "mission_status": started["status"], "dispatch_status": "queued"})
            self.workflows.update_run(user_id, run_id, "running", current_step=index + 1, result={"outputs": outputs})
        self.workflows.update_run(user_id, run_id, "completed", current_step=len(steps),
            result={"outputs": outputs, "completion_semantics": "all_steps_dispatched"}, terminal=True)
        return {"status": "completed", "steps_dispatched": len(outputs), "completion_semantics": "all_steps_dispatched"}
