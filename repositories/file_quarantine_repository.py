"""Owner-scoped persistence for untrusted file quarantine records."""
from database import get_connection


class FileQuarantineRepository:
    def create(self, record):
        conn = get_connection()
        try:
            conn.execute(
                "INSERT INTO file_quarantine_records "
                "(id,user_id,original_filename,object_locator,sha256,byte_size,"
                "detected_media_type,declared_media_type,status,reason_code) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    record["id"], record["user_id"], record["original_filename"],
                    record["object_locator"], record["sha256"], record["byte_size"],
                    record["detected_media_type"], record.get("declared_media_type"),
                    "quarantined", record["reason_code"],
                ),
            )
            conn.commit()
            saved = dict(record)
            saved["status"] = "quarantined"
            return saved
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def get(self, quarantine_id, user_id):
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT id,user_id,original_filename,sha256,byte_size,"
                "detected_media_type,declared_media_type,status,reason_code,created_at "
                "FROM file_quarantine_records WHERE id=? AND user_id=? LIMIT 1",
                (quarantine_id, user_id),
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def list_for_user(self, user_id):
        conn = get_connection()
        try:
            rows = conn.execute(
                "SELECT id,user_id,original_filename,sha256,byte_size,"
                "detected_media_type,declared_media_type,status,reason_code,created_at "
                "FROM file_quarantine_records WHERE user_id=? ORDER BY created_at DESC",
                (user_id,),
            ).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def delete(self, quarantine_id, user_id):
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT object_locator FROM file_quarantine_records "
                "WHERE id=? AND user_id=? AND status='quarantined' LIMIT 1",
                (quarantine_id, user_id),
            ).fetchone()
            if not row:
                return None
            conn.execute(
                "DELETE FROM file_quarantine_records WHERE id=? AND user_id=? "
                "AND status='quarantined'",
                (quarantine_id, user_id),
            )
            conn.commit()
            return row["object_locator"]
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
