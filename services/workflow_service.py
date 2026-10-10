"""Versioned workflow-definition storage; execution is intentionally not implied."""
import json

from database import get_connection


class WorkflowService:
    STEP_TYPES = {"mission", "research", "artifact", "social_content"}

    def create(self, user_id, name, description=None, steps=None):
        name = (name or "").strip()
        if not name or len(name) > 120:
            raise ValueError("Workflow name must be between 1 and 120 characters.")
        steps = self.validate_steps(steps or [], require_nonempty=False)
        conn = get_connection()
        try:
            cursor = conn.execute(
                "INSERT INTO workflows(user_id, name, description, definition_json, version, status) "
                "VALUES (?, ?, ?, ?, 1, 'draft')",
                (user_id, name, description, json.dumps(steps, ensure_ascii=False)),
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
        conn = get_connection()
        try:
            conn.execute(
                "UPDATE workflows SET name=?, description=?, definition_json=?, version=version+1, "
                "status='draft', updated_at=CURRENT_TIMESTAMP WHERE id=? AND user_id=? AND version=?",
                (name, description, json.dumps(steps, ensure_ascii=False), workflow_id, user_id, current["version"]),
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
