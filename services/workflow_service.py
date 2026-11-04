"""Versioned workflow-definition storage; execution is intentionally not implied."""
import json

from database import get_connection
from services.job_queue import JobQueue


class WorkflowService:
    STEP_TYPES = {"mission", "research", "artifact", "social_content", "condition"}

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

    def publish(self, user_id, workflow_id):
        """Create or reuse an immutable snapshot for the currently validated draft."""
        from services.workflow_graph import WorkflowGraphValidator

        conn = get_connection()
        try:
            workflow = conn.execute(
                "SELECT id,user_id,definition_json,version,status,published_version "
                "FROM workflows WHERE id=? AND user_id=? FOR UPDATE",
                (workflow_id, user_id),
            ).fetchone()
            if not workflow:
                return None
            if workflow["status"] not in {"validated", "published"}:
                raise ValueError("Validate the current workflow draft before publishing it.")
            if workflow["status"] == "published" and workflow["published_version"] == workflow["version"]:
                conn.commit()
                return self.get(user_id, workflow_id)

            try:
                steps = json.loads(workflow["definition_json"] or "[]")
            except (TypeError, json.JSONDecodeError) as exc:
                raise ValueError("Workflow definition is malformed and cannot be published.") from exc
            steps = self.validate_steps(steps, require_nonempty=True)
            graph = WorkflowGraphValidator.from_legacy_steps(steps)
            steps_json = json.dumps(steps, ensure_ascii=False, separators=(",", ":"))
            graph_json = json.dumps(graph, ensure_ascii=False, separators=(",", ":"))
            if max(len(steps_json.encode("utf-8")), len(graph_json.encode("utf-8"))) > 100000:
                raise ValueError("Workflow definition exceeds the 100000-byte publication limit.")

            existing = conn.execute(
                "SELECT id FROM workflow_definition_versions WHERE workflow_id=? AND version=?",
                (workflow_id, workflow["version"]),
            ).fetchone()
            if existing:
                version_id = existing["id"]
            else:
                cursor = conn.execute(
                    "INSERT INTO workflow_definition_versions "
                    "(workflow_id,user_id,version,definition_format,definition_json,graph_json,created_by) "
                    "VALUES (?,?,?,'graph_v1',?,?,?)",
                    (workflow_id, user_id, workflow["version"], steps_json, graph_json, user_id),
                )
                version_id = cursor.lastrowid
            conn.execute(
                "UPDATE workflows SET published_version=?,status='published',updated_at=CURRENT_TIMESTAMP "
                "WHERE id=? AND user_id=?",
                (workflow["version"], workflow_id, user_id),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        return self.get(user_id, workflow_id)

    def list_versions(self, user_id, workflow_id):
        conn = get_connection()
        try:
            rows = conn.execute(
                "SELECT id,workflow_id,user_id,version,definition_format,created_at,created_by "
                "FROM workflow_definition_versions WHERE workflow_id=? AND user_id=? "
                "ORDER BY version DESC",
                (workflow_id, user_id),
            ).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def get_run_definition(self, user_id, run_id):
        """Load the immutable definition pinned to a run, or legacy data for old runs."""
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT r.workflow_id,r.workflow_version,r.workflow_version_id,v.definition_json "
                "FROM workflow_runs r LEFT JOIN workflow_definition_versions v "
                "ON v.id=r.workflow_version_id AND v.workflow_id=r.workflow_id AND v.user_id=r.user_id "
                "WHERE r.id=? AND r.user_id=? LIMIT 1",
                (run_id, user_id),
            ).fetchone()
            if not row:
                return None
            if row["workflow_version_id"] is not None:
                if not row["definition_json"]:
                    raise ValueError("The immutable workflow version pinned to this run is unavailable.")
                return {
                    "workflow_id": row["workflow_id"],
                    "version": row["workflow_version"],
                    "workflow_version_id": row["workflow_version_id"],
                    "steps": json.loads(row["definition_json"]),
                    "immutable": True,
                }
            # Historical pre-migration runs did not record a snapshot. Preserve
            # their existing version check rather than guessing an old definition.
            legacy = conn.execute(
                "SELECT definition_json,version FROM workflows WHERE id=? AND user_id=?",
                (row["workflow_id"], user_id),
            ).fetchone()
            if not legacy or legacy["version"] != row["workflow_version"]:
                raise ValueError("Historical workflow definition is no longer available for this run.")
            return {
                "workflow_id": row["workflow_id"],
                "version": row["workflow_version"],
                "workflow_version_id": None,
                "steps": json.loads(legacy["definition_json"] or "[]"),
                "immutable": False,
            }
        finally:
            conn.close()

    def start_run(self, user_id, workflow_id, priority=0):
        workflow = self.get(user_id, workflow_id)
        if not workflow:
            return None
        if workflow["status"] == "validated":
            # Backwards-compatible bridge for existing clients that call
            # validate -> run. The first run publishes an immutable snapshot.
            workflow = self.publish(user_id, workflow_id)
        if not workflow or workflow["status"] != "published":
            raise ValueError("Validate and publish the workflow before executing it.")
        conn = get_connection()
        try:
            snapshot = conn.execute(
                "SELECT id,version FROM workflow_definition_versions "
                "WHERE workflow_id=? AND user_id=? AND version=?",
                (workflow_id, user_id, workflow["published_version"]),
            ).fetchone()
            if not snapshot:
                raise ValueError("The published workflow version is unavailable.")
            cursor = conn.execute(
                "INSERT INTO workflow_runs(workflow_id,user_id,workflow_version,workflow_version_id,status,result_json) "
                "VALUES (?,?,?,?,'queued','{}')",
                (workflow_id, user_id, snapshot["version"], snapshot["id"]),
            )
            run_id = cursor.lastrowid
            JobQueue().enqueue_in_transaction(conn, user_id, "workflow.execute",
                {"workflow_id": workflow_id, "run_id": run_id,
                 "workflow_version": snapshot["version"], "workflow_version_id": snapshot["id"],
                 "step_index": 0},
                idempotency_key=f"workflow-run:{run_id}", priority=priority)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        return self.get_run(user_id, run_id)


    def create_nonmission_step_record(self, user_id, run_id, step_index, step):
        """Persist an execution claim before non-mission side effects."""
        conn = get_connection()
        try:
            existing = conn.execute(
                "SELECT id FROM workflow_step_runs WHERE user_id=? AND workflow_run_id=? AND step_index=?",
                (user_id, run_id, step_index),
            ).fetchone()
            if existing:
                conn.rollback()
                return self.get_step_run(user_id, run_id, step_index), False
            cursor = conn.execute(
                "INSERT INTO workflow_step_runs(workflow_run_id,user_id,step_index,step_id,step_type,status) "
                "VALUES (?,?,?,?,?,'running')",
                (run_id, user_id, step_index, str(step.get("id") or f"step-{step_index + 1}")[:80],
                 step.get("type")),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            existing = conn.execute(
                "SELECT id FROM workflow_step_runs WHERE user_id=? AND workflow_run_id=? AND step_index=?",
                (user_id, run_id, step_index),
            ).fetchone()
            if existing:
                return self.get_step_run(user_id, run_id, step_index), False
            raise
        finally:
            conn.close()
        return self.get_step_run(user_id, run_id, step_index), True

    def complete_nonmission_step(self, user_id, run_id, step_index, result, status="completed"):
        if status not in {"completed", "skipped"}:
            raise ValueError("Non-mission workflow step status must be completed or skipped.")
        conn = get_connection()
        try:
            step = conn.execute(
                "SELECT id,step_id,step_type FROM workflow_step_runs "
                "WHERE user_id=? AND workflow_run_id=? AND step_index=?",
                (user_id, run_id, step_index),
            ).fetchone()
            if not step:
                raise ValueError("Workflow step record is missing.")
            cursor = conn.execute(
                "UPDATE workflow_step_runs SET status=?,result_json=?,error=NULL,"
                "updated_at=CURRENT_TIMESTAMP::text,completed_at=CURRENT_TIMESTAMP::text "
                "WHERE id=? AND status='running'",
                (status, json.dumps(result, ensure_ascii=False, default=str), step["id"]),
            )
            if cursor.rowcount != 1:
                conn.rollback()
                return self.get_run(user_id, run_id)
            run = conn.execute(
                "SELECT workflow_id,workflow_version,workflow_version_id FROM workflow_runs WHERE id=? AND user_id=?",
                (run_id, user_id),
            ).fetchone()
            if not run:
                raise ValueError("Workflow run not found.")
            conn.execute(
                "INSERT INTO decision_ledger(user_id,workflow_run_id,decision_type,decision_json,evidence_json,outcome) "
                "VALUES (?,?,'workflow_step_completion',?,?,?)",
                (user_id, run_id, json.dumps({"step_index": step_index, "step_type": step["step_type"]}),
                 json.dumps([{"source": "workflow_step_record", "step_id": step["step_id"]}]),
                 ("Workflow step skipped by condition." if status == "skipped" else "Workflow step completed.")),
            )
            workflow = None
            if run["workflow_version_id"] is not None:
                workflow = conn.execute(
                    "SELECT definition_json FROM workflow_definition_versions "
                    "WHERE id=? AND workflow_id=? AND user_id=?",
                    (run["workflow_version_id"], run["workflow_id"], user_id),
                ).fetchone()
            else:
                workflow = conn.execute(
                    "SELECT definition_json FROM workflows WHERE id=? AND user_id=?",
                    (run["workflow_id"], user_id),
                ).fetchone()
            if not workflow:
                raise ValueError("Pinned workflow definition is unavailable.")
            steps = json.loads(workflow["definition_json"] or "[]")
            rows = conn.execute(
                "SELECT step_index,step_id,step_type,mission_id,result_json FROM workflow_step_runs "
                "WHERE user_id=? AND workflow_run_id=? AND status IN ('completed','skipped') ORDER BY step_index",
                (user_id, run_id),
            ).fetchall()
            outputs = []
            for item in rows:
                try:
                    output = json.loads(item["result_json"] or "{}")
                except (TypeError, json.JSONDecodeError):
                    output = {}
                outputs.append({"step_index": item["step_index"], "step_id": item["step_id"],
                                "type": item["step_type"], "mission_id": item["mission_id"], "result": output})
            next_index = step_index + 1
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
                     "workflow_version": run["workflow_version"], "step_index": next_index},
                    idempotency_key=f"workflow-run:{run_id}:step:{next_index}",
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        return self.get_run(user_id, run_id)

    def fail_workflow_step(self, user_id, run_id, step_index, error):
        conn = get_connection()
        try:
            conn.execute(
                "UPDATE workflow_step_runs SET status='failed',error=?,updated_at=CURRENT_TIMESTAMP::text,"
                "completed_at=CURRENT_TIMESTAMP::text WHERE user_id=? AND workflow_run_id=? AND step_index=? "
                "AND status IN ('created','running','waiting')",
                (str(error)[:4000], user_id, run_id, step_index),
            )
            conn.execute(
                "UPDATE workflow_runs SET status='failed',current_step=?,error=?,completed_at=CURRENT_TIMESTAMP::text,"
                "updated_at=CURRENT_TIMESTAMP::text WHERE id=? AND user_id=? AND status NOT IN ('completed','cancelled')",
                (step_index, str(error)[:4000], run_id, user_id),
            )
            conn.commit()
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
                "SELECT workflow_id,result_json,workflow_version,workflow_version_id FROM workflow_runs WHERE id=? AND user_id=?",
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
                workflow = None
                if run["workflow_version_id"] is not None:
                    workflow = conn.execute(
                        "SELECT definition_json FROM workflow_definition_versions "
                        "WHERE id=? AND workflow_id=? AND user_id=?",
                        (run["workflow_version_id"], run["workflow_id"], user_id),
                    ).fetchone()
                else:
                    workflow = conn.execute(
                        "SELECT definition_json FROM workflows WHERE id=? AND user_id=?",
                        (run["workflow_id"], user_id),
                    ).fetchone()
                if not workflow:
                    raise ValueError("Pinned workflow definition is unavailable.")
                steps = json.loads(workflow["definition_json"] or "[]")
                completed_steps = conn.execute(
                    "SELECT step_index,step_id,step_type,mission_id,result_json FROM workflow_step_runs "
                    "WHERE user_id=? AND workflow_run_id=? AND status IN ('completed','skipped') ORDER BY step_index",
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
                         "workflow_version": run["workflow_version"], "step_index": next_index},
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
        ids = [step["id"] for step in cleaned]
        if len(set(ids)) != len(ids):
            raise ValueError("Workflow step IDs must be unique.")
        operators = {"equals", "not_equals", "contains", "exists", "gt", "gte", "lt", "lte"}
        for index, step in enumerate(cleaned):
            config = step["config"]
            if step["type"] == "condition":
                source_id = config.get("source_step_id")
                path = config.get("path")
                operator = config.get("operator", "equals")
                if source_id not in ids[:index]:
                    raise ValueError(f"Condition step {index + 1} must reference an earlier step ID.")
                if not isinstance(path, str) or not path.strip() or len(path) > 200:
                    raise ValueError(f"Condition step {index + 1} requires a bounded result path.")
                if operator not in operators:
                    raise ValueError(f"Condition step {index + 1} has an unsupported operator.")
            if "when" in config:
                when = config["when"]
                if (not isinstance(when, dict) or when.get("step_id") not in ids[:index]
                        or not isinstance(when.get("equals"), bool)):
                    raise ValueError(f"Workflow step {index + 1} has an invalid when condition.")
                referenced = cleaned[ids.index(when["step_id"])]
                if referenced["type"] != "condition":
                    raise ValueError(f"Workflow step {index + 1} when condition must reference a condition step.")
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
