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
