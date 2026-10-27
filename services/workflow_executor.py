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
            if record and record["status"] in {"completed", "skipped"}:
                continue
            if record and record["status"] == "failed":
                self.workflows.update_run(user_id, run_id, "failed", current_step=index,
                    error=record.get("error") or f"Workflow step {index + 1} failed.", terminal=True)
                return {"status": "failed", "step_index": index}
            cfg = step.get("config") or {}
            if "when" in cfg:
                when = cfg["when"]
                source_index = next((i for i, candidate in enumerate(steps)
                                     if candidate.get("id") == when["step_id"]), None)
                source = self.workflows.get_step_run(user_id, run_id, source_index) if source_index is not None else None
                if not source or source["status"] not in {"completed", "skipped"}:
                    self.workflows.update_run(user_id, run_id, "failed", current_step=index,
                        error="Conditional step references a condition that has not completed.", terminal=True)
                    return {"status": "failed", "step_index": index, "reason": "condition_missing"}
                matched = source["status"] == "completed" and bool((source.get("result") or {}).get("matched"))
                if matched is not when["equals"]:
                    try:
                        if record is None:
                            self.workflows.create_nonmission_step_record(user_id, run_id, index, step)
                        self.workflows.complete_nonmission_step(
                            user_id, run_id, index,
                            {"skipped": True, "reason": "when_condition_not_met", "condition_step_id": when["step_id"]},
                            status="skipped",
                        )
                        return {"status": "step_skipped", "step_index": index}
                    except Exception as exc:
                        self.workflows.fail_workflow_step(
                            user_id, run_id, index, f"Conditional skip failed ({type(exc).__name__})."
                        )
                        return {"status": "failed", "step_index": index}

            if step.get("type") == "condition":
                try:
                    source_id = cfg["source_step_id"]
                    source_index = next(i for i, candidate in enumerate(steps) if candidate["id"] == source_id)
                    source = self.workflows.get_step_run(user_id, run_id, source_index)
                    if not source or source["status"] not in {"completed", "skipped"}:
                        raise ValueError("Condition source step has not completed.")
                    observed = self._resolve_path(source.get("result") or {}, cfg["path"])
                    operator = cfg.get("operator", "equals")
                    expected = cfg.get("value")
                    try:
                        matched = {
                            "equals": lambda: observed == expected,
                            "not_equals": lambda: observed != expected,
                            "contains": lambda: observed is not None and expected in observed,
                            "exists": lambda: observed is not None,
                            "gt": lambda: float(observed) > float(expected),
                            "gte": lambda: float(observed) >= float(expected),
                            "lt": lambda: float(observed) < float(expected),
                            "lte": lambda: float(observed) <= float(expected),
                        }[operator]()
                    except (TypeError, ValueError):
                        matched = False
                    if record is None:
                        self.workflows.create_nonmission_step_record(user_id, run_id, index, step)
                    condition_result = {"matched": bool(matched), "source_step_id": source_id,
                                        "path": cfg["path"], "operator": operator,
                                        "observed": observed, "expected": expected}
                    self.workflows.complete_nonmission_step(user_id, run_id, index, condition_result)
                    return {"status": "condition_evaluated", "step_index": index, "matched": bool(matched)}
                except (KeyError, StopIteration, ValueError) as exc:
                    self.workflows.fail_workflow_step(user_id, run_id, index, str(exc))
                    return {"status": "failed", "step_index": index}

            if step.get("type") in {"research", "artifact", "social_content"}:
                try:
                    step_record, created = self.workflows.create_nonmission_step_record(user_id, run_id, index, step)
                    if not created and (not step_record or step_record["status"] not in {"running", "created"}):
                        error = "Workflow step is not in a replay-safe state."
                        self.workflows.fail_workflow_step(user_id, run_id, index, error)
                        return {"status": "failed", "step_index": index, "reason": "unsafe_step_replay"}
                    cfg = step.get("config") or {}
                    idempotency_key = f"workflow-step:{run_id}:{index}"
                    if step["type"] == "research":
                        from services.research_service import ResearchService
                        result = ResearchService().create(
                            user_id, cfg.get("query") or cfg.get("topic") or "",
                            cfg.get("summary") or "", cfg.get("source_urls") or [],
                            cfg.get("mission_id"), idempotency_key=idempotency_key,
                        )
                    elif step["type"] == "artifact":
                        from services.artifact_service import ArtifactService
                        result = ArtifactService().create(
                            user_id, cfg.get("name") or "", cfg.get("content") or "",
                            cfg.get("artifact_type", "text"), cfg.get("mission_id"),
                            idempotency_key=idempotency_key,
                        )
                        result.pop("path", None)
                    else:
                        from services.social_content_service import SocialContentService
                        result = SocialContentService().create(
                            user_id, cfg.get("platform") or "", cfg.get("title") or "",
                            cfg.get("content") or "", cfg.get("hashtags") or [],
                            idempotency_key=idempotency_key,
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

    @staticmethod
    def _resolve_path(value, path):
        current = value
        for part in str(path).split("."):
            if isinstance(current, dict):
                current = current.get(part)
            elif isinstance(current, list):
                try:
                    current = current[int(part)]
                except (ValueError, IndexError):
                    return None
            else:
                return None
        return current
