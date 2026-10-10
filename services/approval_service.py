"""Durable, owner-scoped approval and single-execution lifecycle."""
import json
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status

from database import get_connection
from logging_setup import get_logger

logger = get_logger("audit")
DEFAULT_APPROVAL_TTL_MINUTES = 15


def _utc_now():
    return datetime.now(timezone.utc)


def _iso(value):
    return value.isoformat(timespec="seconds")


class ApprovalService:
    def create(self, user_id, action, resource, payload=None, ttl_minutes=DEFAULT_APPROVAL_TTL_MINUTES):
        approval_id = str(uuid.uuid4())
        now = _utc_now()
        expires_at = _iso(now + timedelta(minutes=ttl_minutes))
        payload_json = json.dumps(payload or {}, separators=(",", ":"), ensure_ascii=False)
        conn = get_connection()
        try:
            conn.execute(
                "INSERT INTO approvals(id, user_id, action, resource, status, payload_json, "
                "execution_status, expires_at) VALUES (?, ?, ?, ?, 'pending', ?, 'pending', ?)",
                (approval_id, user_id, action, resource, payload_json, expires_at),
            )
            conn.commit()
        finally:
            conn.close()

        logger.info(
            "Approval created: id=%s user=%s action=%s expires_at=%s",
            approval_id, user_id, action, expires_at,
        )
        return self.get_for_user(approval_id, user_id)

    def list_pending(self, user_id):
        conn = get_connection()
        try:
            rows = conn.execute(
                "SELECT id, user_id, action, resource, status, payload_json, execution_status, "
                "expires_at, created_at FROM approvals "
                "WHERE user_id=? AND status='pending' ORDER BY created_at DESC",
                (user_id,),
            ).fetchall()
            results = []
            for row in rows:
                item = dict(row)
                item["payload"] = self._decode_payload(item.pop("payload_json", None))
                results.append(item)
            return results
        finally:
            conn.close()

    def get_for_user(self, approval_id, user_id):
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT id, user_id, action, resource, status, payload_json, execution_status, "
                "expires_at, decided_at, executed_at, execution_result, created_at "
                "FROM approvals WHERE id=? AND user_id=? LIMIT 1",
                (approval_id, user_id),
            ).fetchone()
            if not row:
                return None
            item = dict(row)
            item["payload"] = self._decode_payload(item.pop("payload_json", None))
            if item.get("execution_result"):
                try:
                    item["execution_result"] = json.loads(item["execution_result"])
                except (TypeError, json.JSONDecodeError):
                    item["execution_result"] = {"detail": "Stored execution result could not be decoded."}
            return item
        finally:
            conn.close()

    def decide(self, approval_id, user_id, approved):
        record = self.get_for_user(approval_id, user_id)
        if not record:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Approval not found.")
        if record["status"] != "pending":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Approval already {record['status']}.",
            )
        if self._is_expired(record.get("expires_at")):
            conn = get_connection()
            try:
                conn.execute(
                    "UPDATE approvals SET status='expired' WHERE id=? AND user_id=? AND status='pending'",
                    (approval_id, user_id),
                )
                conn.commit()
            finally:
                conn.close()
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Approval expired. Submit the operation again.")

        new_status = "approved" if approved else "rejected"
        conn = get_connection()
        try:
            cursor = conn.execute(
                "UPDATE approvals SET status=?, decided_at=? "
                "WHERE id=? AND user_id=? AND status='pending'",
                (new_status, _iso(_utc_now()), approval_id, user_id),
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

        logger.info("Approval %s decided: %s by user %s", approval_id, new_status, user_id)
        return self.get_for_user(approval_id, user_id)

    def claim_for_execution(self, approval_id, user_id):
        """Atomically claim an approved operation so only one request can execute it."""
        record = self.get_for_user(approval_id, user_id)
        if not record:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Approval not found.")
        if record["status"] != "approved":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Approval has not been approved.")
        if self._is_expired(record.get("expires_at")):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Approval expired before execution.")
        if record.get("execution_status") != "pending":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Operation cannot be executed again (state: {record.get('execution_status')}).",
            )

        conn = get_connection()
        try:
            cursor = conn.execute(
                "UPDATE approvals SET execution_status='running' "
                "WHERE id=? AND user_id=? AND status='approved' AND execution_status='pending' AND expires_at>?",
                (approval_id, user_id, _iso(_utc_now())),
            )
            if cursor.rowcount != 1:
                conn.rollback()
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Operation is expired or already claimed for execution.",
                )
            conn.commit()
        finally:
            conn.close()
        return record

    def mark_execution_result(self, approval_id, user_id, execution_status, result):
        if execution_status not in {"completed", "failed", "indeterminate"}:
            raise ValueError("Unsupported approval execution status.")
        serialized = json.dumps(result, default=str, ensure_ascii=False)[:16000]
        conn = get_connection()
        try:
            cursor = conn.execute(
                "UPDATE approvals SET execution_status=?, executed_at=?, execution_result=? "
                "WHERE id=? AND user_id=? AND execution_status='running'",
                (execution_status, _iso(_utc_now()), serialized, approval_id, user_id),
            )
            if cursor.rowcount != 1:
                conn.rollback()
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Execution state changed unexpectedly.")
            conn.commit()
        finally:
            conn.close()
        return self.get_for_user(approval_id, user_id)

    def is_approved(self, approval_id):
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT status FROM approvals WHERE id=? LIMIT 1", (approval_id,)
            ).fetchone()
            return bool(row) and row["status"] == "approved"
        finally:
            conn.close()

    @staticmethod
    def _decode_payload(payload_json):
        if not payload_json:
            return {}
        try:
            value = json.loads(payload_json)
            return value if isinstance(value, dict) else {}
        except (TypeError, json.JSONDecodeError):
            return {}

    @staticmethod
    def _is_expired(expires_at):
        if not expires_at:
            return True
        try:
            value = datetime.fromisoformat(expires_at)
            if value.tzinfo is None:
                value = value.replace(tzinfo=timezone.utc)
            return value <= _utc_now()
        except (TypeError, ValueError):
            return True
