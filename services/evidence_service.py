"""Owner-scoped evidence records; review status is not an independent fact check."""
from database import get_connection
from urllib.parse import urlsplit


class EvidenceService:
    STATUSES = {"unverified", "reviewed", "rejected"}

    def create(self, user_id, claim, source_url, source_excerpt="", confidence=None, mission_id=None):
        claim = (claim or "").strip()
        source_url = (source_url or "").strip()
        if not claim or len(claim) > 10000:
            raise ValueError("Evidence claim must be between 1 and 10000 characters.")
        if len(source_excerpt or "") > 20000:
            raise ValueError("Source excerpt exceeds the 20000-character limit.")
        parts = urlsplit(source_url)
        if parts.scheme not in {"http", "https"} or not parts.hostname or parts.username or parts.password:
            raise ValueError("Evidence source must be an HTTP/HTTPS URL without embedded credentials.")
        if confidence is not None and not 0 <= float(confidence) <= 1:
            raise ValueError("Confidence must be between 0 and 1.")
        if mission_id is not None and not self._owns_mission(user_id, mission_id):
            raise ValueError("Mission not found for this user.")
        conn = get_connection()
        try:
            cursor = conn.execute(
                "INSERT INTO evidence(mission_id, user_id, claim, evidence_text, source_reference, confidence, validation_status) "
                "VALUES (?, ?, ?, ?, ?, ?, 'unverified')",
                (mission_id, user_id, claim, source_url, source_excerpt or "", confidence),
            )
            evidence_id = cursor.lastrowid
            conn.commit()
        finally:
            conn.close()
        return self.get(user_id, evidence_id)

    def list_for_user(self, user_id):
        conn = get_connection()
        try:
            rows = conn.execute(
                "SELECT id, mission_id, user_id, claim, source_reference AS source_url, evidence_text AS source_excerpt, confidence, "
                "validation_status, created_at FROM evidence WHERE user_id=? ORDER BY created_at DESC, id DESC",
                (user_id,),
            ).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def get(self, user_id, evidence_id):
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT id, mission_id, user_id, claim, source_url, source_excerpt, confidence, "
                "validation_status, created_at FROM evidence WHERE id=? AND user_id=? LIMIT 1",
                (evidence_id, user_id),
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def review(self, user_id, evidence_id, status):
        if status not in {"reviewed", "rejected"}:
            raise ValueError("Review status must be reviewed or rejected.")
        conn = get_connection()
        try:
            cursor = conn.execute(
                "UPDATE evidence SET validation_status=? WHERE id=? AND user_id=?",
                (status, evidence_id, user_id),
            )
            conn.commit()
            found = cursor.rowcount == 1
        finally:
            conn.close()
        return self.get(user_id, evidence_id) if found else None

    @staticmethod
    def _owns_mission(user_id, mission_id):
        conn = get_connection()
        try:
            return conn.execute(
                "SELECT id FROM missions WHERE id=? AND user_id=? LIMIT 1",
                (mission_id, user_id),
            ).fetchone() is not None
        finally:
            conn.close()
