"""Sequential workflow execution with durable child-mission recovery."""
from services.workflow_service import WorkflowService
from services.mission_service import MissionService
from database import get_connection


class WorkflowExecutor:
    def __init__(self, workflows=None, missions=None):
        self.workflows = workflows or WorkflowService()
        self.missions = missions or MissionService()

    def execute(self, job):
        payload = job.get("payload") or {}
        user_id = job["user_id"]
        try:
            workflow_id = int(payload.get("workflow_id", 0))
            run_id = int(payload.get("run_id", 0))
            expected_version = int(payload.get("workflow_version", -1))
        except (TypeError, ValueError):
            return {"status": "invalid_payload"}
        workflow = self.workflows.get(user_id, workflow_id)
        run = self.workflows.get_run(user_id, run_id)
        if not workflow or not run or run["status"] not in {"queued", "running"}:
            return {"status": "stale_or_missing"}
        if workflow["version"] != expected_version or run["workflow_version"] != workflow["version"]:
            self.workflows.update_run(user_id, run_id, "failed",
                error="Workflow version changed after enqueue.", terminal=True)
            return {"status": "failed", "reason": "version_mismatch"}

        steps = workflow.get("steps") or []
        outputs = (run.get("result") or {}).get("outputs", [])
        if not isinstance(outputs, list):
            outputs = []
        self.workflows.update_run(user_id, run_id, "running")
        for index, step in enumerate(steps):
            record = self.workflows.get_step_run(user_id, run_id, index)
            if record and record["status"] == "completed":
                continue
            if record and record["status"] == "failed":
                self.workflows.update_run(user_id, run_id, "failed", current_step=index,
                    error=record.get("error") or f"Workflow step {index + 1} failed.", terminal=True)
                return {"status": "failed", "step_index": index}
            if step.get("type") != "mission":
                self.workflows.update_run(user_id, run_id, "failed", current_step=index,
                    result={"outputs": outputs},
                    error=f"No trusted executor is enabled for step type '{step.get('type')}'.", terminal=True)
                return {"status": "failed", "step_index": index}
            try:
                if record is None:
                    record = self.workflows.create_step_mission(user_id, run_id, index, step)
                mission_id = record.get("mission_id")
                if not mission_id:
                    raise ValueError("Workflow step has no recoverable child mission.")
                mission = self.missions.get(user_id, int(mission_id))
                if not mission:
                    raise ValueError("Workflow child mission is missing.")
                if mission["status"] == "completed":
                    result = mission.get("runs", [{}])[0].get("result") or {}
                    self.workflows.on_child_mission_finished(user_id, mission_id, "completed", result=result)
                    return {"status": "reconciled_child_completion", "step_index": index}
                if mission["status"] in {"failed", "cancelled"}:
                    error = f"Child mission ended with status {mission['status']}."
                    self.workflows.on_child_mission_finished(user_id, mission_id, "failed", error=error)
                    self.workflows.update_run(user_id, run_id, "failed", current_step=index,
                        error=error, terminal=True)
                    return {"status": "failed", "step_index": index}
                if mission["status"] == "pending":
                    self.missions.start_run(user_id, int(mission_id))
                conn = get_connection()
                try:
                    conn.execute(
                        "UPDATE workflow_step_runs SET status='running',updated_at=CURRENT_TIMESTAMP::text "
                        "WHERE user_id=? AND workflow_run_id=? AND step_index=? AND status IN ('created','running')",
                        (user_id, run_id, index),
                    )
                    conn.commit()
                finally:
                    conn.close()
                self.workflows.update_run(user_id, run_id, "waiting", current_step=index)
                return {"status": "waiting_for_child_mission", "step_index": index, "mission_id": mission_id}
            except ValueError as exc:
                self.workflows.update_run(user_id, run_id, "failed", current_step=index,
                    result={"outputs": outputs}, error=f"Workflow step {index + 1}: {exc}", terminal=True)
                return {"status": "failed", "step_index": index}

        self.workflows.update_run(user_id, run_id, "completed", current_step=len(steps),
            result={"outputs": outputs, "completion_semantics": "all_steps_completed"}, terminal=True)
        return {"status": "completed", "steps_completed": len(steps),
                "completion_semantics": "all_steps_completed"}
