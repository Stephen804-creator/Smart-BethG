from database import get_connection


class ConversationRepository:
    def create(self, user_id, title=None):
        conn = get_connection()
        try:
            cur = conn.execute(
                "INSERT INTO conversations(user_id, title) VALUES (?, ?)",
                (user_id, title),
            )
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()

    def get(self, conversation_id, user_id):
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT id, user_id, title, created_at, updated_at FROM conversations "
                "WHERE id=? AND user_id=? LIMIT 1",
                (conversation_id, user_id),
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def list_for_user(self, user_id, limit=50):
        conn = get_connection()
        try:
            rows = conn.execute(
                "SELECT id, title, created_at, updated_at FROM conversations "
                "WHERE user_id=? ORDER BY updated_at DESC LIMIT ?",
                (user_id, limit),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def touch(self, conversation_id):
        conn = get_connection()
        try:
            conn.execute(
                "UPDATE conversations SET updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (conversation_id,),
            )
            conn.commit()
        finally:
            conn.close()

    def set_title(self, conversation_id, title):
        conn = get_connection()
        try:
            conn.execute(
                "UPDATE conversations SET title=? WHERE id=?",
                (title, conversation_id),
            )
            conn.commit()
        finally:
            conn.close()

    def add_message(self, conversation_id, role, content, provider=None, model=None, tokens_in=None, tokens_out=None):
        conn = get_connection()
        try:
            cur = conn.execute(
                "INSERT INTO messages(conversation_id, role, content, provider, model, tokens_in, tokens_out) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (conversation_id, role, content, provider, model, tokens_in, tokens_out),
            )
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()

    def list_messages(self, conversation_id, limit=200):
        conn = get_connection()
        try:
            rows = conn.execute(
                "SELECT id, role, content, provider, model, created_at FROM messages "
                "WHERE conversation_id=? ORDER BY id ASC LIMIT ?",
                (conversation_id, limit),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def usage_totals_for_user(self, user_id):
        """
        Real totals, summed directly from stored per-message token counts
        (which themselves come straight from each provider's own API
        response - see providers/*.py). Not an estimate.
        """
        conn = get_connection()
        try:
            rows = conn.execute(
                """
                SELECT m.provider, m.model,
                       SUM(COALESCE(m.tokens_in, 0)) AS input_tokens,
                       SUM(COALESCE(m.tokens_out, 0)) AS output_tokens,
                       COUNT(*) AS message_count
                FROM messages m
                JOIN conversations c ON c.id = m.conversation_id
                WHERE c.user_id = ? AND m.role = 'assistant'
                GROUP BY m.provider, m.model
                ORDER BY input_tokens + output_tokens DESC
                """,
                (user_id,),
            ).fetchall()
            by_model = [dict(r) for r in rows]
            totals = {
                "input_tokens": sum(r["input_tokens"] or 0 for r in by_model),
                "output_tokens": sum(r["output_tokens"] or 0 for r in by_model),
                "message_count": sum(r["message_count"] or 0 for r in by_model),
            }
            return {"totals": totals, "by_model": by_model}
        finally:
            conn.close()
