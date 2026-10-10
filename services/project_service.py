"""Owner-scoped project CRUD and lifecycle."""
from fastapi import HTTPException

from database import get_connection


class ProjectService:
    VALID_STATUSES = {"active", "paused", "archived"}

    def create(self, user_id, name, description=None):
        name = (name or "").strip()
        if not name or len(name) > 120:
            raise ValueError("Project name must be between 1 and 120 characters.")
        conn = get_connection()
        try:
            cur = conn.execute(
                "INSERT INTO projects(user_id, name, description, status, updated_at) "
                "VALUES (?, ?, ?, 'active', CURRENT_TIMESTAMP)",
                (user_id, name, description),
            )
            project_id = cur.lastrowid
            conn.commit()
        finally:
            conn.close()
        return self.get(user_id, project_id)

    def list_for_user(self, user_id):
        conn = get_connection()
        try:
            rows = conn.execute(
                "SELECT id, user_id, name, description, status, created_at, updated_at "
                "FROM projects WHERE user_id=? ORDER BY updated_at DESC, id DESC",
                (user_id,),
            ).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def get(self, user_id, project_id):
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT id, user_id, name, description, status, created_at, updated_at "
                "FROM projects WHERE id=? AND user_id=? LIMIT 1",
                (project_id, user_id),
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def update(self, user_id, project_id, fields):
        current = self.get(user_id, project_id)
        if not current:
            return None
        name = fields.get("name", current["name"])
        description = fields.get("description", current["description"])
        status = fields.get("status", current["status"])
        if not isinstance(name, str) or not name.strip() or len(name.strip()) > 120:
            raise ValueError("Project name must be between 1 and 120 characters.")
        if status not in self.VALID_STATUSES:
            raise ValueError("Invalid project status.")
        conn = get_connection()
        try:
            conn.execute(
                "UPDATE projects SET name=?, description=?, status=?, updated_at=CURRENT_TIMESTAMP "
                "WHERE id=? AND user_id=?",
                (name.strip(), description, status, project_id, user_id),
            )
            conn.commit()
        finally:
            conn.close()
        return self.get(user_id, project_id)

    def archive(self, user_id, project_id):
        current = self.get(user_id, project_id)
        if not current:
            return False
        conn = get_connection()
        try:
            conn.execute(
                "UPDATE projects SET status='archived', updated_at=CURRENT_TIMESTAMP "
                "WHERE id=? AND user_id=?",
                (project_id, user_id),
            )
            conn.commit()
        finally:
            conn.close()
        return True
