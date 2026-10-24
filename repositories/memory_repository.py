import json

from database import get_connection


class MemoryRepository:
    MEMORY_COLUMNS = "id, user_id, scope, scope_ref, title, content, source, created_at, memory_type, confidence, source_ref, metadata_json, expires_at, updated_at"

    @staticmethod
    def _deserialize(row):
        if not row:
            return None
        value = dict(row)
        raw = value.pop("metadata_json", None)
        try:
            value["metadata"] = json.loads(raw) if raw else {}
        except (TypeError, ValueError):
            value["metadata"] = {}
        return value

    def create(self, user_id, content, scope="user", scope_ref=None, title=None, source="explicit",
               memory_type="episodic", confidence=1.0, source_ref=None, metadata=None, expires_at=None):
        metadata_json = json.dumps(metadata or {}, ensure_ascii=False, separators=(",", ":"))
        conn = get_connection()
        try:
            cur = conn.execute(
                "INSERT INTO memory(user_id, scope, scope_ref, title, content, source, memory_type, confidence, source_ref, metadata_json, expires_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
                (user_id, scope, scope_ref, title, content, source, memory_type, confidence, source_ref, metadata_json, expires_at),
            )
            memory_id = cur.lastrowid
            conn.commit()
            return memory_id
        finally:
            conn.close()

    def get(self, memory_id, user_id):
        conn = get_connection()
        try:
            row = conn.execute(
                f"SELECT {self.MEMORY_COLUMNS} FROM memory WHERE id=? AND user_id=? LIMIT 1", (memory_id, user_id)
            ).fetchone()
            return self._deserialize(row)
        finally:
            conn.close()

    def list_for_user(self, user_id):
        """Governance view - every memory of every scope belonging to this user."""
        conn = get_connection()
        try:
            rows = conn.execute(
                f"SELECT {self.MEMORY_COLUMNS} FROM memory WHERE user_id=? ORDER BY COALESCE(updated_at, created_at) DESC, id DESC",
                (user_id,),
            ).fetchall()
            return [self._deserialize(row) for row in rows]
        finally:
            conn.close()

    def list_by_scope(self, user_id, scope, scope_ref=None):
        conn = get_connection()
        try:
            if scope_ref is None:
                rows = conn.execute(
                    f"SELECT {self.MEMORY_COLUMNS} FROM memory WHERE user_id=? AND scope=? ORDER BY COALESCE(updated_at, created_at) DESC, id DESC",
                    (user_id, scope),
                ).fetchall()
            else:
                rows = conn.execute(
                    f"SELECT {self.MEMORY_COLUMNS} FROM memory WHERE user_id=? AND scope=? AND scope_ref=? ORDER BY COALESCE(updated_at, created_at) DESC, id DESC",
                    (user_id, scope, scope_ref),
                ).fetchall()
            return [self._deserialize(row) for row in rows]
        finally:
            conn.close()

    def delete(self, memory_id, user_id):
        conn = get_connection()
        try:
            cur = conn.execute("DELETE FROM memory WHERE id=? AND user_id=?", (memory_id, user_id))
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()

    def delete_all_for_user(self, user_id):
        conn = get_connection()
        try:
            cur = conn.execute("DELETE FROM memory WHERE user_id=?", (user_id,))
            conn.commit()
            return cur.rowcount
        finally:
            conn.close()
