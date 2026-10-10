from database import get_connection


class MemoryRepository:
    def create(self, user_id, content, scope="user", scope_ref=None, title=None, source="explicit"):
        conn = get_connection()
        try:
            cur = conn.execute(
                "INSERT INTO memory(user_id, scope, scope_ref, title, content, source) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, scope, scope_ref, title, content, source),
            )
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()

    def get(self, memory_id, user_id):
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT * FROM memory WHERE id=? AND user_id=? LIMIT 1", (memory_id, user_id)
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def list_for_user(self, user_id):
        """Every memory of every scope belonging to this user - the governance view."""
        conn = get_connection()
        try:
            rows = conn.execute(
                "SELECT * FROM memory WHERE user_id=? ORDER BY id DESC", (user_id,)
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def list_by_scope(self, user_id, scope, scope_ref=None):
        conn = get_connection()
        try:
            if scope_ref is None:
                rows = conn.execute(
                    "SELECT * FROM memory WHERE user_id=? AND scope=? ORDER BY id DESC",
                    (user_id, scope),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM memory WHERE user_id=? AND scope=? AND scope_ref=? ORDER BY id DESC",
                    (user_id, scope, scope_ref),
                ).fetchall()
            return [dict(r) for r in rows]
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
