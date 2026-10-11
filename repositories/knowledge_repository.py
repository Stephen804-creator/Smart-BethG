import json

from database import get_connection


class KnowledgeRepository:
    def create_chunk(self, user_id, file_id, workspace, chunk_index, content, embedding=None, embedding_model=None):
        conn = get_connection()
        try:
            embedding_json = json.dumps(embedding) if embedding is not None else None
            cur = conn.execute(
                "INSERT INTO knowledge_chunks(user_id, file_id, workspace, chunk_index, content, embedding, embedding_model) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (user_id, file_id, workspace, chunk_index, content, embedding_json, embedding_model),
            )
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()

    def delete_for_file(self, file_id, user_id):
        conn = get_connection()
        try:
            cur = conn.execute(
                "DELETE FROM knowledge_chunks WHERE file_id=? AND user_id=?", (file_id, user_id)
            )
            conn.commit()
            return cur.rowcount
        finally:
            conn.close()

    def list_for_user(self, user_id, workspace=None):
        conn = get_connection()
        try:
            if workspace:
                rows = conn.execute(
                    "SELECT * FROM knowledge_chunks WHERE user_id=? AND workspace=? ORDER BY id",
                    (user_id, workspace),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM knowledge_chunks WHERE user_id=? ORDER BY id", (user_id,)
                ).fetchall()
            return [self._deserialize(dict(r)) for r in rows]
        finally:
            conn.close()

    def search_candidates(self, user_id, terms, workspace=None, limit=200):
        """Find bounded matching chunks in SQL; this path never calls an embedding provider."""
        terms = [str(term).lower() for term in terms if term]
        if not terms:
            return []
        clauses = " OR ".join("LOWER(content) LIKE ?" for _ in terms)
        like_params = [f"%{term}%" for term in terms]
        workspace_order = "CASE WHEN workspace=? THEN 0 ELSE 1 END, " if workspace else ""
        conn = get_connection()
        try:
            if getattr(conn, "is_postgres", False):
                import re
                fts_terms = []
                for term in terms:
                    fts_terms.extend(re.findall(r"[a-zA-Z0-9]+", term.lower()))
                tsquery = " | ".join(dict.fromkeys(fts_terms))
                where = "(to_tsvector('simple', content) @@ to_tsquery('simple', ?) OR (" + clauses + "))"
                params = [tsquery, *like_params, user_id]
            else:
                where = "(" + clauses + ")"
                params = [*like_params, user_id]
            if workspace:
                params.append(workspace)
            params.append(max(1, min(int(limit), 500)))
            rows = conn.execute(
                "SELECT * FROM knowledge_chunks WHERE " + where + " AND user_id=? "
                "ORDER BY " + workspace_order + "id DESC LIMIT ?",
                tuple(params),
            ).fetchall()
            return [self._deserialize(dict(row)) for row in rows]
        finally:
            conn.close()

    def count_for_user(self, user_id):
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT COUNT(*) AS c FROM knowledge_chunks WHERE user_id=?", (user_id,)
            ).fetchone()
            return row["c"]
        finally:
            conn.close()

    @staticmethod
    def _deserialize(row):
        row["embedding"] = json.loads(row["embedding"]) if row.get("embedding") else None
        return row
