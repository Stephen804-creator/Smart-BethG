from database import get_connection


class FileRepository:
    def create(self, user_id, filename, path, file_type, source="upload"):
        conn = get_connection()
        try:
            cur = conn.execute(
                "INSERT INTO files(user_id, filename, path, file_type, source, status) "
                "VALUES (?, ?, ?, ?, ?, 'stored')",
                (user_id, filename, path, file_type, source),
            )
            file_id = cur.lastrowid
            if str(filename).lower().endswith(".pdf"):
                conn.execute(
                    "INSERT INTO file_extractions(file_id,user_id,status) VALUES (?,?, 'pending') "
                    "ON CONFLICT(file_id) DO NOTHING",
                    (file_id, user_id),
                )
                from services.job_queue import JobQueue
                JobQueue().enqueue_in_transaction(
                    conn, user_id, "file.extract_pdf", {"file_id": file_id},
                    "file-pdf-extract:" + str(file_id), priority=1, max_attempts=3,
                )
            conn.commit()
            return file_id
        finally:
            conn.close()

    def get(self, file_id, user_id):
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT * FROM files WHERE id=? AND user_id=? LIMIT 1", (file_id, user_id)
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def list_for_user(self, user_id):
        conn = get_connection()
        try:
            rows = conn.execute(
                "SELECT * FROM files WHERE user_id=? ORDER BY id DESC", (user_id,)
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def search_by_filename(self, user_id, query):
        conn = get_connection()
        try:
            rows = conn.execute(
                "SELECT * FROM files WHERE user_id=? AND filename LIKE ? ORDER BY id DESC",
                (user_id, f"%{query}%"),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def delete(self, file_id, user_id):
        conn = get_connection()
        try:
            cur = conn.execute("DELETE FROM files WHERE id=? AND user_id=?", (file_id, user_id))
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()
