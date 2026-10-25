"""Versioned workflow-definition storage; execution is intentionally not implied."""
import json

from database import get_connection
from services.job_queue import JobQueue


class WorkflowService:
    STEP_TYPES = {"mission", "research", "artifact", "social_content"}

    def create(self, user_id, name, description=None, steps=None):
        name = (name or "").strip()
        if not name or len(name) > 120:
            raise ValueError("Workflow name must be between 1 and 120 characters.")
        steps = self.validate_steps(steps or [], require_nonempty=False)
        definition_json = json.dumps(steps, ensure_ascii=False)
        if len(definition_json) > 100000:
            raise ValueError("Workflow definition exceeds the 100000-character limit.")
        conn = get_connection()
        try:
            cursor = conn.execute(
                "INSERT INTO workflows(user_id, name, description, definition_json, version, status) "
                "VALUES (?, ?, ?, ?, 1, 'draft')",
                (user_id, name, description, definition_json),
            )
            workflow_id = cursor.lastrowid
            conn.commit()
        finally:
            conn.close()
        return self.get(user_id, workflow_id)

    def list_for_user(self, user_id):
        conn = get_connection()
        try:
            rows = conn.execute(
                "SELECT id, user_id, name, description, definition_json, version, status, created_at, updated_at "
                "FROM workflows WHERE user_id=? ORDER BY updated_at DESC, id DESC",
                (user_id,),
            ).fetchall()
            return [self._decode(row) for row in rows]
        finally:
            conn.close()

    def get(self, user_id, workflow_id):
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT id, user_id, name, description, definition_json, version, status, created_at, updated_at "
                "FROM workflows WHERE id=? AND user_id=? LIMIT 1",
                (workflow_id, user_id),
            ).fetchone()
            return self._decode(row) if row else None
        finally:
            conn.close()

    def update(self, user_id, workflow_id, fields):
        current = self.get(user_id, workflow_id)
        if not current:
            return None
        name = fields.get("name", current["name"])
        description = fields.get("description", current["description"])
        steps = fields.get("steps", current["steps"])
        name = (name or "").strip()
        if not name or len(name) > 120:
            raise ValueError("Workflow name must be between 1 and 120 characters.")
        steps = self.validate_steps(steps, require_nonempty=False)
        definition_json = json.dumps(steps, ensure_ascii=False)
        if len(definition_json) > 100000:
            raise ValueError("Workflow definition exceeds the 100000-character limit.")
        conn = get_connection()
        try:
            cursor = conn.execute(
                "UPDATE workflows SET name=?, description=?, definition_json=?, version=version+1, "
                "status='draft', updated_at=CURRENT_TIMESTAMP WHERE id=? AND user_id=? AND version=?",
                (name, description, definition_json, workflow_id, user_id, current["version"]),
            )
            if cursor.rowcount != 1:
                conn.rollback()
                raise ValueError("Workflow changed concurrently. Refresh and try again.")
            conn.commit()
        finally:
            conn.close()
        return self.get(user_id, workflow_id)

    def validate(self, user_id, workflow_id):
        workflow = self.get(user_id, workflow_id)
        if not workflow:
            return None
        steps = self.validate_steps(workflow["steps"], require_nonempty=True)
        conn = get_connection()
        try:
            conn.execute(
                "UPDATE workflows SET status='validated', updated_at=CURRENT_TIMESTAMP WHERE id=? AND user_id=?",
                (workflow_id, user_id),
            )
            conn.commit()
        finally:
            conn.close()
        workflow["steps"] = steps
        workflow["status"] = "validated"
        return workflow

    def start_run(self, user_id, workflow_id, priority=0):
        workflow = self.get(user_id, workflow_id)
        if not workflow:
            return None
        if workflow["status"] != "validated":
            raise ValueError("Validate the workflow before executing it.")
        steps = self.validate_steps(workflow["steps"], require_nonempty=True)
        unsupported = [step["type"] for step in steps if step["type"] != "mission"]
        if unsupported:
            raise ValueError("Execution adapters are not enabled yet for: " + ", ".join(sorted(set(unsupported))))
        conn = get_connection()
        try:
            cursor = conn.execute("INSERT INTO workflow_runs(workflow_id,user_id,workflow_version,status,result_json) VALUES (?,?,?,'queued','{}')",
                                  (workflow_id, user_id, workflow["version"]))
            run_id = cursor.lastrowid
            JobQueue().enqueue_in_transaction(conn, user_id, "workflow.execute",
                {"workflow_id": workflow_id, "run_id": run_id, "workflow_version": workflow["version"]},
                idempotency_key=f"workflow-run:{run_id}", priority=priority)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        return self.get_run(user_id, run_id)


    def get_step_run(self, user_id, run_id, step_index):
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT id,workflow_run_id,user_id,step_index,step_id,step_type,status,mission_id,result_json,error,created_at,updated_at,completed_at "
                "FROM workflow_step_runs WHERE user_id=? AND workflow_run_id=? AND step_index=? LIMIT 1",
                (user_id, run_id, step_index),
            ).fetchone()
            if not row:
                return None
            item = dict(row)
            try:
                item["result"] = json.loads(item.pop("result_json") or "{}")
            except (TypeError, json.JSONDecodeError):
                item["result"] = {}
                item.pop("result_json", None)
            return item
        finally:
            conn.close()

    def create_step_mission(self, user_id, run_id, step_index, step):
        """Atomically create a child mission and its unique workflow-step record."""
        from services.mission_service import MissionService
        missions = MissionService()
        config = step.get("config") or {}
        objective = str(config.get("objective") or "").strip()
        priority = config.get("priority", "normal")
        project_id = config.get("project_id")
        if not objective or len(objective) > 12000:
            raise ValueError("Mission step objective must be between 1 and 12000 characters.")
        if priority not in missions.VALID_PRIORITIES:
            raise ValueError("Invalid mission priority in workflow step.")
        if project_id is not None and not missions._owns_project(user_id, project_id):
            raise ValueError("Workflow step project not found for this user.")
        mission_steps = missions.validate_steps(config.get("steps") or [])
        conn = get_connection()
        try:
            run = conn.execute(
                "SELECT id,status FROM workflow_runs WHERE id=? AND user_id=?",
                (run_id, user_id),
            ).fetchone()
            if not run or run["status"] not in {"queued", "running"}:
                raise ValueError("Workflow run is no longer executable.")
            existing = conn.execute(
                "SELECT id,mission_id FROM workflow_step_runs WHERE user_id=? AND workflow_run_id=? AND step_index=?",
                (user_id, run_id, step_index),
            ).fetchone()
            if existing:
                conn.rollback()
                return self.get_step_run(user_id, run_id, step_index)
            cursor = conn.execute(
                "INSERT INTO missions(user_id,project_id,objective,status,priority,plan_json,updated_at) "
                "VALUES (?,?,?,'pending',?,?,CURRENT_TIMESTAMP)",
                (user_id, project_id, objective, priority, json.dumps(mission_steps, ensure_ascii=False)),
            )
            mission_id = cursor.lastrowid
            conn.execute(
                "INSERT INTO workflow_step_runs(workflow_run_id,user_id,step_index,step_id,step_type,status,mission_id) "
                "VALUES (?,?,?,?,?,'created',?)",
                (run_id, user_id, step_index, str(step.get("id") or f"step-{step_index + 1}")[:80],
                 step.get("type", "mission"), mission_id),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            existing = conn.execute(
                "SELECT id FROM workflow_step_runs WHERE user_id=? AND workflow_run_id=? AND step_index=?",
                (user_id, run_id, step_index),
            ).fetchone()
            if existing:
                return self.get_step_run(user_id, run_id, step_index)
            raise
        finally:
            conn.close()
        return self.get_step_run(user_id, run_id, step_index)

    def on_child_mission_finished(self, user_id, mission_id, status, result=None, error=None, conn=None):
        """Atomically advance the parent workflow when a child mission terminates."""
        own_connection = conn is None
        if own_connection:
            conn = get_connection()
        try:
            step = conn.execute(
                "SELECT id,workflow_run_id,step_index FROM workflow_step_runs "
                "WHERE user_id=? AND mission_id=? LIMIT 1",
                (user_id, mission_id),
            ).fetchone()
            if not step:
                if own_connection:
                    conn.rollback()
                return False
            final_step_status = "completed" if status == "completed" else "failed"
            step_update = conn.execute(
                "UPDATE workflow_step_runs SET status=?,result_json=?,error=?,updated_at=CURRENT_TIMESTAMP::text,"
                "completed_at=CURRENT_TIMESTAMP::text WHERE id=? AND status IN ('created','running','waiting')",
                (final_step_status, json.dumps(result or {}, ensure_ascii=False, default=str),
                 str(error)[:4000] if error else None, step["id"]),
            )
            run_id = step["workflow_run_id"]
            if step_update.rowcount == 1:
                conn.execute(
                    "INSERT INTO decision_ledger(user_id,mission_id,workflow_run_id,decision_type,decision_json,evidence_json,outcome) "
                    "VALUES (?,?,?,'workflow_step_completion',?,?,?)",
                    (user_id, mission_id, run_id,
                     json.dumps({"step_index": step["step_index"], "status": final_step_status}),
                     json.dumps([{"source": "mission_run", "mission_id": mission_id}]),
                     str(error)[:2000] if error else "Child mission completed."),
                )
            run = conn.execute(
                "SELECT workflow_id,result_json,workflow_version FROM workflow_runs WHERE id=? AND user_id=?",
                (run_id, user_id),
            ).fetchone()
            if not run:
                if own_connection:
                    conn.rollback()
                return False
            if status != "completed":
                conn.execute(
                    "UPDATE workflow_runs SET status='failed',error=?,completed_at=CURRENT_TIMESTAMP::text,"
                    "updated_at=CURRENT_TIMESTAMP::text WHERE id=? AND user_id=? AND status NOT IN ('completed','cancelled')",
                    (str(error or "A child mission failed.")[:4000], run_id, user_id),
                )
            else:
                workflow = conn.execute(
                    "SELECT definition_json FROM workflows WHERE id=? AND user_id=?",
                    (run["workflow_id"], user_id),
                ).fetchone()
                steps = json.loads(workflow["definition_json"] or "[]") if workflow else []
                completed_steps = conn.execute(
                    "SELECT step_index,step_id,step_type,mission_id,result_json FROM workflow_step_runs "
                    "WHERE user_id=? AND workflow_run_id=? AND status='completed' ORDER BY step_index",
                    (user_id, run_id),
                ).fetchall()
                outputs = []
                for item in completed_steps:
                    try:
                        output = json.loads(item["result_json"] or "{}")
                    except (TypeError, json.JSONDecodeError):
                        output = {}
                    outputs.append({"step_index": item["step_index"], "step_id": item["step_id"],
                                    "type": item["step_type"], "mission_id": item["mission_id"], "result": output})
                next_index = int(step["step_index"]) + 1
                if next_index >= len(steps):
                    conn.execute(
                        "UPDATE workflow_runs SET status='completed',current_step=?,result_json=?,error=NULL,"
                        "completed_at=CURRENT_TIMESTAMP::text,updated_at=CURRENT_TIMESTAMP::text "
                        "WHERE id=? AND user_id=? AND status NOT IN ('completed','cancelled')",
                        (len(steps), json.dumps({"outputs": outputs, "completion_semantics": "all_steps_completed"},
                                                ensure_ascii=False, default=str), run_id, user_id),
                    )
                else:
                    conn.execute(
                        "UPDATE workflow_runs SET status='queued',current_step=?,result_json=?,error=NULL,"
                        "updated_at=CURRENT_TIMESTAMP::text WHERE id=? AND user_id=? AND status NOT IN ('completed','cancelled','failed')",
                        (next_index, json.dumps({"outputs": outputs}, ensure_ascii=False, default=str), run_id, user_id),
                    )
                    from services.job_queue import JobQueue
                    JobQueue().enqueue_in_transaction(
                        conn, user_id, "workflow.execute",
                        {"workflow_id": run["workflow_id"], "run_id": run_id,
                         "workflow_version": run["workflow_version"]},
                        idempotency_key=f"workflow-run:{run_id}:step:{next_index}",
                    )
            if own_connection:
                conn.commit()
            return True
        except Exception:
            if own_connection:
                conn.rollback()
            raise
        finally:
            if own_connection:
                conn.close()

    def get_run(self, user_id, run_id):
        conn = get_connection()
        try:
            row = conn.execute("SELECT id,workflow_id,user_id,workflow_version,status,current_step,result_json,error,started_at,completed_at,created_at,updated_at FROM workflow_runs WHERE id=? AND user_id=? LIMIT 1",
                               (run_id, user_id)).fetchone()
            return self._decode_run(row) if row else None
        finally:
            conn.close()

    def list_runs(self, user_id, workflow_id, limit=30):
        conn = get_connection()
        try:
            rows = conn.execute("SELECT id,workflow_id,user_id,workflow_version,status,current_step,result_json,error,started_at,completed_at,created_at,updated_at FROM workflow_runs WHERE workflow_id=? AND user_id=? ORDER BY id DESC LIMIT ?",
                                (workflow_id, user_id, max(1, min(100, int(limit))))).fetchall()
            return [self._decode_run(row) for row in rows]
        finally:
            conn.close()

    def update_run(self, user_id, run_id, status, current_step=None, result=None, error=None, terminal=False):
        if status not in {"running", "waiting", "completed", "failed", "cancelled"}:
            raise ValueError("Invalid workflow run status.")
        conn = get_connection()
        try:
            if not conn.execute("SELECT id FROM workflow_runs WHERE id=? AND user_id=?", (run_id, user_id)).fetchone():
                return None
            conn.execute("UPDATE workflow_runs SET status=?,current_step=COALESCE(?,current_step),result_json=COALESCE(?,result_json),error=?,started_at=CASE WHEN ?='running' THEN COALESCE(started_at,CURRENT_TIMESTAMP::text) ELSE started_at END,completed_at=CASE WHEN ? THEN CURRENT_TIMESTAMP::text ELSE completed_at END,updated_at=CURRENT_TIMESTAMP::text WHERE id=? AND user_id=?",
                (status, current_step, json.dumps(result, ensure_ascii=False) if result is not None else None,
                 str(error)[:4000] if error else None, status, bool(terminal), run_id, user_id))
            conn.commit()
        finally:
            conn.close()
        return self.get_run(user_id, run_id)

    @staticmethod
    def _decode_run(row):
        item = dict(row)
        try:
            item["result"] = json.loads(item.pop("result_json") or "{}")
        except (TypeError, json.JSONDecodeError):
            item["result"] = {}
            item.pop("result_json", None)
        return item

    def archive(self, user_id, workflow_id):
        workflow = self.get(user_id, workflow_id)
        if not workflow:
            return False
        conn = get_connection()
        try:
            conn.execute(
                "UPDATE workflows SET status='archived', updated_at=CURRENT_TIMESTAMP WHERE id=? AND user_id=?",
                (workflow_id, user_id),
            )
            conn.commit()
        finally:
            conn.close()
        return True

    @classmethod
    def validate_steps(cls, steps, require_nonempty):
        if not isinstance(steps, list) or len(steps) > 50:
            raise ValueError("Workflow steps must be a list of at most 50 items.")
        if require_nonempty and not steps:
            raise ValueError("Add at least one workflow step before validating.")
        cleaned = []
        for index, step in enumerate(steps):
            if not isinstance(step, dict):
                raise ValueError(f"Workflow step {index + 1} must be an object.")
            step_type = step.get("type")
            if step_type not in cls.STEP_TYPES:
                raise ValueError(f"Workflow step {index + 1} has an unsupported type.")
            config = step.get("config", {})
            if not isinstance(config, dict):
                raise ValueError(f"Workflow step {index + 1} config must be an object.")
            cleaned.append({
                "id": str(step.get("id") or f"step-{index + 1}")[:80],
                "type": step_type,
                "config": config,
            })
        return cleaned

    @staticmethod
    def _decode(row):
        item = dict(row)
        try:
            item["steps"] = json.loads(item.pop("definition_json") or "[]")
        except (TypeError, json.JSONDecodeError):
            item["steps"] = []
            item.pop("definition_json", None)
        return item
