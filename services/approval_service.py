"""
Persistent, user-scoped approval decisions for Smart BethG.
"""
import uuid

from fastapi import HTTPException, status

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

        logger.info(
            "Approval created: id=%s user=%s action=%s resource=%s",
            approval_id, user_id, action, resource,
        )
        return self._get(approval_id)

    def list_pending(self, user_id):
        conn = get_connection()
        try:
            rows = conn.execute(
                "SELECT id, user_id, action, resource, status, created_at "
                "FROM approvals WHERE user_id=? AND status='pending' "
                "ORDER BY created_at DESC",
                (user_id,),
            ).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def decide(self, approval_id, user_id, approved):
        new_status = "approved" if approved else "rejected"
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT user_id, status FROM approvals WHERE id=? LIMIT 1",
                (approval_id,),
            ).fetchone()

            # Do not reveal whether another user's approval ID exists.
            if not row or row["user_id"] != user_id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Approval not found.",
                )
            if row["status"] != "pending":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Approval already {row['status']}.",
                )

            # Conditional update prevents two concurrent requests from both
            # deciding the same pending approval.
            cursor = conn.execute(
                "UPDATE approvals SET status=? "
                "WHERE id=? AND user_id=? AND status='pending'",
                (new_status, approval_id, user_id),
            )
            if cursor.rowcount != 1:
                conn.rollback()
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Approval was already decided. Refresh and try again.",
                )
            conn.commit()
        finally:
            conn.close()

        logger.info(
            "Approval %s decided: %s by user %s",
            approval_id, new_status, user_id,
        )
        return self._get(approval_id)

    def is_approved(self, approval_id):
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT status FROM approvals WHERE id=? LIMIT 1",
                (approval_id,),
            ).fetchone()
            return bool(row) and row["status"] == "approved"
        finally:
            conn.close()

    def _get(self, approval_id):
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT id, user_id, action, resource, status, created_at "
                "FROM approvals WHERE id=? LIMIT 1",
                (approval_id,),
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()
