"""Owner-scoped persistence and atomic release for quarantined uploads."""
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
            # Persist the inspection job in the same transaction as the
            # quarantine record. There can be no accepted upload with a missing
            # queue job due to a process crash between two commits.
            from services.job_queue import JobQueue
            JobQueue().enqueue_in_transaction(
                conn,
                record["user_id"],
                "file.inspect",
                {"quarantine_id": record["id"], "sha256": record["sha256"]},
                "file-inspect:" + record["id"],
                priority=2,
                max_attempts=5,
            )
            conn.commit()
            saved = dict(record)
            saved["status"] = "quarantined"
            saved["inspection_status"] = "queued"
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
                "detected_media_type,declared_media_type,status,reason_code,"
                "inspection_status,inspection_attempts,inspection_error_code,created_at "
                "FROM file_quarantine_records WHERE id=? AND user_id=? LIMIT 1",
                (quarantine_id, user_id),
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def get_for_inspection(self, quarantine_id, user_id):
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT id,user_id,original_filename,object_locator,sha256,byte_size,"
                "detected_media_type,status FROM file_quarantine_records "
                "WHERE id=? AND user_id=? LIMIT 1",
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
                "detected_media_type,declared_media_type,status,reason_code,"
                "inspection_status,inspection_attempts,inspection_error_code,created_at "
                "FROM file_quarantine_records WHERE user_id=? ORDER BY created_at DESC",
                (user_id,),
            ).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def set_inspection_state(self, quarantine_id, user_id, state, attempts=None,
                             engine=None, error_code=None):
        allowed = {"queued", "checking", "clean", "rejected", "failed"}
        if state not in allowed:
            raise ValueError("Invalid file inspection state.")
        conn = get_connection()
        try:
            cursor = conn.execute(
                "UPDATE file_quarantine_records SET inspection_status=?,"
                "inspection_attempts=COALESCE(?,inspection_attempts),"
                "inspection_engine=COALESCE(?,inspection_engine),"
                "inspection_error_code=?,"
                "inspected_at=CASE WHEN ? IN ('clean','rejected','failed') "
                "THEN CURRENT_TIMESTAMP ELSE inspected_at END "
                "WHERE id=? AND user_id=? AND status='quarantined'",
                (state, attempts, engine, error_code, state, quarantine_id, user_id),
            )
            conn.commit()
            return cursor.rowcount == 1
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def release(self, quarantine_id, user_id, filename, locator, file_type):
        """Create the trusted file row and mark quarantine released atomically."""
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT id FROM file_quarantine_records WHERE id=? AND user_id=? "
                "AND status='quarantined' AND inspection_status='checking' LIMIT 1",
                (quarantine_id, user_id),
            ).fetchone()
            if not row:
                raise RuntimeError("Quarantine record is no longer eligible for release.")
            created = conn.execute(
                "INSERT INTO files(user_id,filename,path,file_type,source,status) "
                "VALUES (?,?,?,?,?,'stored')",
                (user_id, filename, locator, file_type, "quarantine_release"),
            )
            file_id = created.lastrowid
            if filename.lower().endswith(".pdf"):
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
            updated = conn.execute(
                "UPDATE file_quarantine_records SET status='released',"
                "inspection_status='clean',inspection_engine='clamav',"
                "inspected_at=CURRENT_TIMESTAMP,inspection_error_code=NULL,"
                "released_file_id=? WHERE id=? AND user_id=? AND status='quarantined'",
                (file_id, quarantine_id, user_id),
            )
            if updated.rowcount != 1:
                raise RuntimeError("Quarantine record changed before release.")
            conn.commit()
            return file_id
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def retry_inspection(self, quarantine_id, user_id):
        """Requeue a failed check without asking the user to upload the file again."""
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT inspection_retry_generation FROM file_quarantine_records "
                "WHERE id=? AND user_id=? AND status='quarantined' "
                "AND inspection_status='failed' LIMIT 1",
                (quarantine_id, user_id),
            ).fetchone()
            if not row:
                conn.rollback()
                return False
            generation = int(row["inspection_retry_generation"] or 0) + 1
            cursor = conn.execute(
                "UPDATE file_quarantine_records SET inspection_status='queued',"
                "inspection_attempts=0,inspection_retry_generation=?,"
                "inspection_error_code=NULL,inspected_at=NULL "
                "WHERE id=? AND user_id=? AND status='quarantined' "
                "AND inspection_status='failed'",
                (generation, quarantine_id, user_id),
            )
            if cursor.rowcount != 1:
                conn.rollback()
                return False
            from services.job_queue import JobQueue
            JobQueue().enqueue_in_transaction(
                conn, user_id, "file.inspect",
                {"quarantine_id": quarantine_id,
                 "sha256": self._sha256_for_retry(conn, quarantine_id, user_id)},
                f"file-inspect:{quarantine_id}:retry:{generation}",
                priority=2, max_attempts=5,
            )
            conn.commit()
            return True
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def _sha256_for_retry(conn, quarantine_id, user_id):
        row = conn.execute(
            "SELECT sha256 FROM file_quarantine_records WHERE id=? AND user_id=? LIMIT 1",
            (quarantine_id, user_id),
        ).fetchone()
        if not row:
            raise RuntimeError("Quarantine record disappeared while retrying inspection.")
        return row["sha256"]

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
            deleted = conn.execute(
                "DELETE FROM file_quarantine_records WHERE id=? AND user_id=? "
                "AND status='quarantined'",
                (quarantine_id, user_id),
            )
            if deleted.rowcount != 1:
                conn.rollback()
                return None
            conn.commit()
            return row["object_locator"]
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
