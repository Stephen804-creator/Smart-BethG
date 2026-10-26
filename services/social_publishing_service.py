"""Scheduled social publishing with explicit approval and fail-closed adapters."""
import json
import uuid
from datetime import datetime, timezone, timedelta

from database import get_connection
from services.social_content_service import SocialContentService


class SocialPublishingService:
    """Adapter injection is intentionally explicit; no platform is faked as connected."""
    def __init__(self, adapters=None):
        self.adapters = adapters or {}
        self.content = SocialContentService()

    def schedule(self, user_id, content_id, scheduled_at, idempotency_key):
        if not isinstance(idempotency_key, str) or not idempotency_key.strip() or len(idempotency_key) > 200:
            raise ValueError("A 1–200 character idempotency key is required.")
        try:
            when = datetime.fromisoformat(scheduled_at.replace("Z", "+00:00"))
        except (AttributeError, ValueError):
            raise ValueError("scheduled_at must be an ISO-8601 timestamp with a timezone.")
        if when.tzinfo is None:
            raise ValueError("scheduled_at must include a timezone.")
        now = datetime.now(timezone.utc)
        when = when.astimezone(timezone.utc)
        if when < now + timedelta(seconds=30) or when > now + timedelta(days=365):
            raise ValueError("Schedule must be at least 30 seconds in the future and within one year.")
        item = self.content.get(user_id, content_id)
        if not item:
            raise LookupError("Social content not found.")
        if item["status"] != "approved":
            raise PermissionError("Only approved social content can be scheduled.")
        conn = get_connection()
        try:
            row = conn.execute(
                "INSERT INTO social_publish_jobs(id,user_id,content_id,platform,status,scheduled_at,idempotency_key) "
                "VALUES (?,?,?,?, 'scheduled',?,?) ON CONFLICT(user_id,idempotency_key) DO NOTHING "
                "RETURNING id,user_id,content_id,platform,status,scheduled_at,idempotency_key,created_at",
                (str(uuid.uuid4()), user_id, content_id, item["platform"], when, idempotency_key.strip()),
            ).fetchone()
            if row:
                conn.commit()
                return dict(row)
            existing = conn.execute(
                "SELECT id,user_id,content_id,platform,status,scheduled_at,idempotency_key,created_at "
                "FROM social_publish_jobs WHERE user_id=? AND idempotency_key=?",
                (user_id, idempotency_key.strip()),
            ).fetchone()
            conn.commit()
            if not existing:
                raise RuntimeError("Could not resolve schedule idempotency conflict.")
            return dict(existing)
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def list_for_user(self, user_id, limit=50):
        conn = get_connection()
        try:
            rows = conn.execute(
                "SELECT id,content_id,platform,status,scheduled_at,external_post_id,last_error_code,created_at,updated_at "
                "FROM social_publish_jobs WHERE user_id=? ORDER BY scheduled_at DESC LIMIT ?",
                (user_id, max(1, min(100, int(limit)))),
            ).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def cancel(self, user_id, schedule_id):
        conn = get_connection()
        try:
            cursor = conn.execute(
                "UPDATE social_publish_jobs SET status='cancelled',updated_at=CURRENT_TIMESTAMP "
                "WHERE id=? AND user_id=? AND status='scheduled'",
                (schedule_id, user_id),
            )
            conn.commit()
            return cursor.rowcount == 1
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def process_due(self, limit=10):
        """Claim due schedules once. Missing adapters and ambiguous results are blocked, never retried blindly."""
        conn = get_connection()
        try:
            conn.execute("BEGIN")
            rows = conn.execute(
                "SELECT id,user_id,content_id,platform,idempotency_key FROM social_publish_jobs "
                "WHERE status='scheduled' AND scheduled_at<=CURRENT_TIMESTAMP "
                "ORDER BY scheduled_at FOR UPDATE SKIP LOCKED LIMIT ?",
                (max(1, min(50, int(limit))),),
            ).fetchall()
            claimed = [dict(row) for row in rows]
            for row in claimed:
                conn.execute(
                    "UPDATE social_publish_jobs SET status='publishing',updated_at=CURRENT_TIMESTAMP WHERE id=? AND status='scheduled'",
                    (row["id"],),
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

        outcomes = []
        for row in claimed:
            adapter = self.adapters.get(row["platform"])
            if adapter is None:
                self._finish(row["id"], "blocked", None, "publisher_not_configured")
                outcomes.append({"id": row["id"], "status": "blocked", "reason": "publisher_not_configured"})
                continue
            try:
                content = self.content.get(row["user_id"], row["content_id"])
                if not content or content["status"] != "approved":
                    self._finish(row["id"], "blocked", None, "content_not_approved")
                    outcomes.append({"id": row["id"], "status": "blocked", "reason": "content_not_approved"})
                    continue
                result = adapter.publish(user_id=row["user_id"], content=content,
                                         idempotency_key=row["idempotency_key"])
                external_id = (result or {}).get("external_post_id")
                if not external_id or len(str(external_id)) > 500:
                    self._finish(row["id"], "blocked", None, "ambiguous_publish_result")
                    outcomes.append({"id": row["id"], "status": "blocked", "reason": "ambiguous_publish_result"})
                    continue
                self._finish(row["id"], "published", str(external_id), None)
                outcomes.append({"id": row["id"], "status": "published"})
            except Exception as exc:
                # A transport failure may happen after the remote platform accepted
                # the post. Do not automatically retry and create a duplicate post.
                self._finish(row["id"], "blocked", None, "ambiguous_publish_result")
                outcomes.append({"id": row["id"], "status": "blocked",
                                 "reason": "ambiguous_publish_result",
                                 "error_type": type(exc).__name__})
        return outcomes

    @staticmethod
    def _finish(schedule_id, status, external_post_id, error_code):
        conn = get_connection()
        try:
            conn.execute(
                "UPDATE social_publish_jobs SET status=?,external_post_id=?,last_error_code=?,updated_at=CURRENT_TIMESTAMP "
                "WHERE id=? AND status='publishing'",
                (status, external_post_id, error_code, schedule_id),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
