from database import get_connection


class TrainingExportRepository:
    def fetch_exportable_messages(self, since=None, until=None, limit=1000):
        """
        Returns {conversation_id: [{"role":, "content":}, ...]}, ordered
        within each conversation. Only conversations containing at least
        one assistant message from a real, configured provider are
        included at all (provider IS NOT NULL AND provider != 'agent') -
        see TrainingExportService's module docstring for why.
        """
        conn = get_connection()
        try:
            qualifying_ids_query = (
                "SELECT DISTINCT conversation_id FROM messages "
                "WHERE role='assistant' AND provider IS NOT NULL AND provider != 'agent'"
            )
            params = []
            if since:
                qualifying_ids_query += " AND created_at >= ?"
                params.append(since)
            if until:
                qualifying_ids_query += " AND created_at <= ?"
                params.append(until)
            qualifying_ids_query += " ORDER BY conversation_id DESC LIMIT ?"
            params.append(limit)

            conversation_ids = [
                row["conversation_id"] for row in conn.execute(qualifying_ids_query, params).fetchall()
            ]
            if not conversation_ids:
                return {}

            placeholders = ",".join("?" for _ in conversation_ids)
            rows = conn.execute(
                f"""
                SELECT conversation_id, role, content FROM messages
                WHERE conversation_id IN ({placeholders})
                  AND role IN ('user', 'assistant')
                  AND (role = 'user' OR (provider IS NOT NULL AND provider != 'agent'))
                ORDER BY conversation_id, id
                """,
                conversation_ids,
            ).fetchall()

            grouped = {}
            for row in rows:
                grouped.setdefault(row["conversation_id"], []).append(
                    {"role": row["role"], "content": row["content"]}
                )
            return grouped
        finally:
            conn.close()
