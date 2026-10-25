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
            expected_step = int(payload.get("step_index", 0))
        except (TypeError, ValueError):
            return {"status": "invalid_payload"}
        workflow = self.workflows.get(user_id, workflow_id)
        run = self.workflows.get_run(user_id, run_id)
        if not workflow or not run or run["status"] not in {"queued", "running"}:
            return {"status": "stale_or_missing"}
        if expected_step != int(run.get("current_step") or 0):
            return {"status": "stale_step_job"}
        if workflow["version"] != expected_version or run["workflow_version"] != workflow["version"]:
            self.workflows.update_run(user_id, run_id, "failed",
                error="Workflow version changed after enqueue.", terminal=True)
            return {"status": "failed", "reason": "version_mismatch"}

        steps = workflow.get("steps") or []
        outputs = (run.get("result") or {}).get("outputs", [])
        if not isinstance(outputs, list):
            outputs = []
        self.workflows.update_run(user_id, run_id, "running")
        for index in range(expected_step, len(steps)):
            step = steps[index]
            record = self.workflows.get_step_run(user_id, run_id, index)
            if record and record["status"] == "completed":
                continue
            if record and record["status"] == "failed":
                self.workflows.update_run(user_id, run_id, "failed", current_step=index,
                    error=record.get("error") or f"Workflow step {index + 1} failed.", terminal=True)
                return {"status": "failed", "step_index": index}
            if step.get("type") in {"research", "artifact", "social_content"}:
                try:
                    step_record, created = self.workflows.create_nonmission_step_record(user_id, run_id, index, step)
                    if not created:
                        error = "A prior worker attempt may have performed this side effect; replay is suppressed for safety."
                        self.workflows.fail_workflow_step(user_id, run_id, index, error)
                        return {"status": "failed", "step_index": index, "reason": "ambiguous_side_effect_replay"}
                    cfg = step.get("config") or {}
                    if step["type"] == "research":
                        from services.research_service import ResearchService
                        result = ResearchService().create(
                            user_id, cfg.get("query") or cfg.get("topic") or "",
                            cfg.get("summary") or "", cfg.get("source_urls") or [],
                            cfg.get("mission_id"),
                        )
                    elif step["type"] == "artifact":
                        from services.artifact_service import ArtifactService
                        result = ArtifactService().create(
                            user_id, cfg.get("name") or "", cfg.get("content") or "",
                            cfg.get("artifact_type", "text"), cfg.get("mission_id"),
                        )
                        result.pop("path", None)
                    else:
                        from services.social_content_service import SocialContentService
                        result = SocialContentService().create(
                            user_id, cfg.get("platform") or "", cfg.get("title") or "",
                            cfg.get("content") or "", cfg.get("hashtags") or [],
                        )
                    self.workflows.complete_nonmission_step(user_id, run_id, index, result)
                    return {"status": "step_completed", "step_index": index, "step_type": step["type"]}
                except ValueError as exc:
                    self.workflows.fail_workflow_step(user_id, run_id, index, str(exc))
                    return {"status": "failed", "step_index": index}
                except Exception as exc:
                    self.workflows.fail_workflow_step(
                        user_id, run_id, index, f"Workflow adapter failed ({type(exc).__name__}); inspect operational logs."
                    )
                    return {"status": "failed", "step_index": index}
            if step.get("type") != "mission":
                self.workflows.update_run(user_id, run_id, "failed", current_step=index,
                    result={"outputs": outputs},
                    error=f"No trusted executor is enabled for step type '{step.get('type')}'.", terminal=True)
                return {"status": "failed", "step_index": index}
            mission_id = record.get("mission_id") if record else None
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
                # Two workers may observe the same durable step during a lease
                # replay. A concurrently started child is not a workflow failure.
                latest = self.missions.get(user_id, int(mission_id)) if mission_id else None
                if latest and latest["status"] in {"running", "awaiting_approval"}:
                    self.workflows.update_run(user_id, run_id, "waiting", current_step=index)
                    return {"status": "waiting_for_child_mission", "step_index": index, "mission_id": mission_id}
                if latest and latest["status"] == "completed":
                    self.workflows.on_child_mission_finished(
                        user_id, mission_id, "completed",
                        result=(latest.get("runs") or [{}])[0].get("result") or {},
                    )
                    return {"status": "reconciled_child_completion", "step_index": index}
                self.workflows.update_run(user_id, run_id, "failed", current_step=index,
                    result={"outputs": outputs}, error=f"Workflow step {index + 1}: {exc}", terminal=True)
                return {"status": "failed", "step_index": index}

        self.workflows.update_run(user_id, run_id, "completed", current_step=len(steps),
            result={"outputs": outputs, "completion_semantics": "all_steps_completed"}, terminal=True)
        return {"status": "completed", "steps_completed": len(steps),
                "completion_semantics": "all_steps_completed"}
