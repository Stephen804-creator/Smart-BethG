from database import get_connection


class Repository:
    def list(self, user_id):
        conn = get_connection()
        rows = conn.execute(
            "SELECT * FROM audit_events WHERE user_id=? ORDER BY id DESC", (user_id,)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def list_all(self, limit=200):
        """Admin-only - across every user. See routes/audit.py."""
        conn = get_connection()
        rows = conn.execute(
            "SELECT * FROM audit_events ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def create(self, user_id, agent_id, action, resource, decision, risk_level, details):
        conn = get_connection()
        conn.execute(
            "INSERT INTO audit_events(user_id, agent_id, action, resource, decision, risk_level, details) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (user_id, agent_id, action, resource, decision, risk_level, details),
        )
        conn.commit()
        conn.close()
