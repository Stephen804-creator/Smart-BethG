"""Owner-scoped PDF extraction state and bounded text persistence."""
from database import get_connection


class FileExtractionRepository:
    def get_for_user(self, file_id, user_id):
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT file_id,user_id,status,extracted_text,page_count,error_code "
                "FROM file_extractions WHERE file_id=? AND user_id=? LIMIT 1",
                (file_id, user_id),
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def complete(self, file_id, user_id, extracted_text, page_count):
        conn = get_connection()
        try:
            cursor = conn.execute(
                "UPDATE file_extractions SET status='ready',extracted_text=?,"
                "page_count=?,error_code=NULL,updated_at=CURRENT_TIMESTAMP "
                "WHERE file_id=? AND user_id=?",
                (extracted_text, page_count, file_id, user_id),
            )
            conn.commit()
            return cursor.rowcount == 1
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def reconcile_abandoned(self):
        """Close pending extraction states whose durable jobs exhausted their leases."""
        conn = get_connection()
        try:
            cursor = conn.execute(
                "UPDATE file_extractions AS extraction SET status='failed',"
                "error_code='worker_lease_exhausted',updated_at=CURRENT_TIMESTAMP "
                "WHERE extraction.status='pending' AND NOT EXISTS ("
                "SELECT 1 FROM background_jobs j WHERE j.user_id=extraction.user_id "
                "AND j.job_type='file.extract_pdf' "
                "AND j.idempotency_key='file-pdf-extract:' || extraction.file_id "
                "AND j.status IN ('queued','running')) "
                "AND EXISTS (SELECT 1 FROM background_jobs j "
                "WHERE j.user_id=extraction.user_id AND j.job_type='file.extract_pdf' "
                "AND j.idempotency_key='file-pdf-extract:' || extraction.file_id "
                "AND j.status='failed')"
            )
            conn.commit()
            return cursor.rowcount
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def fail(self, file_id, user_id, error_code):
        conn = get_connection()
        try:
            cursor = conn.execute(
                "UPDATE file_extractions SET status='failed',extracted_text=NULL,"
                "error_code=?,updated_at=CURRENT_TIMESTAMP "
                "WHERE file_id=? AND user_id=?",
                (str(error_code)[:100], file_id, user_id),
            )
            conn.commit()
            return cursor.rowcount == 1
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
