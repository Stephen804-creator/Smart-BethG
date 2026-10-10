"""
Smart BethG - Approval Service

Previously this stored approvals in a plain Python dict on the service
instance, and api/dependencies.get_approval_service() created a brand
new instance on every single request - meaning an approval created on
one request was already gone by the time any later request tried to
read or decide it. This was a real, live bug (approvals could never
actually work), not just an incomplete feature.

Now backed by the `approvals` table, which already existed in the
schema but nothing wrote to it.
"""
import uuid

from database import get_connection
from logging_setup import get_logger

logger = get_logger("audit")


class ApprovalService:
    def create(self, user_id, action, resource):
        approval_id = str(uuid.uuid4())
        conn = get_connection()
        try:
            conn.execute(
                "INSERT INTO approvals(id, user_id, action, resource, status) "
                "VALUES (?, ?, ?, ?, 'pending')",
                (approval_id, user_id, action, resource),
            )
            conn.commit()
        finally:
            conn.close()
        logger.info("Approval created: id=%s user=%s action=%s resource=%s", approval_id, user_id, action, resource)
        return self._get(approval_id)

    def list_pending(self, user_id):
        conn = get_connection()
        try:
            rows = conn.execute(
                "SELECT * FROM approvals WHERE user_id=? AND status='pending' ORDER BY created_at DESC",
                (user_id,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def decide(self, approval_id, user_id, approved):
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT * FROM approvals WHERE id=? LIMIT 1", (approval_id,)
            ).fetchone()
            if not row or row["user_id"] != user_id:
                return {"error": "Approval not found."}
            if row["status"] != "pending":
                return {"error": f"Approval already {row['status']}."}

            new_status = "approved" if approved else "rejected"
            conn.execute("UPDATE approvals SET status=? WHERE id=?", (new_status, approval_id))
            conn.commit()
        finally:
            conn.close()
        logger.info("Approval %s decided: %s by user %s", approval_id, new_status, user_id)
        return self._get(approval_id)

    def is_approved(self, approval_id):
        conn = get_connection()
        try:
            row = conn.execute("SELECT status FROM approvals WHERE id=? LIMIT 1", (approval_id,)).fetchone()
            return bool(row) and row["status"] == "approved"
        finally:
            conn.close()

    def _get(self, approval_id):
        conn = get_connection()
        try:
            row = conn.execute("SELECT * FROM approvals WHERE id=? LIMIT 1", (approval_id,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()
