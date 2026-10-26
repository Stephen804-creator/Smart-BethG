"""Approval-gated social publishing orchestration.

The registry intentionally starts empty: no platform is reported as publishable
until a trusted, reviewed provider adapter is installed and configured.
"""
import json
import uuid

from database import get_connection
from services.approval_service import ApprovalService
from services.social_content_service import SocialContentService


class SocialPublisherRegistry:
    def __init__(self):
        self._adapters = {}

    def register(self, platform, adapter):
        if not isinstance(platform, str) or not platform.strip():
            raise ValueError("A platform key is required.")
        if not callable(getattr(adapter, "publish", None)):
            raise ValueError("Publisher adapter must implement publish(content, idempotency_key).")
        key = platform.strip().lower()
        if key in self._adapters:
            raise ValueError("A publisher adapter is already registered for this platform.")
        self._adapters[key] = adapter

    def get(self, platform):
        return self._adapters.get((platform or "").strip().lower())

    def catalog(self):
        return [{"platform": key, "configured": True} for key in sorted(self._adapters)]


class SocialPublishingService:
    def __init__(self, publishers=None, approvals=None, content_service=None):
        self.publishers = publishers or SocialPublisherRegistry()
        self.approvals = approvals or ApprovalService()
        self.content = content_service or SocialContentService()

    def catalog(self):
        supported = self.content.PLATFORMS
        configured = {item["platform"] for item in self.publishers.catalog()}
        return [{"platform": platform, "publisher_configured": platform in configured}
                for platform in sorted(supported)]

    def request_publish(self, user_id, content_id, idempotency_key=None):
        item = self.content.get(user_id, content_id)
        if not item:
            return None
        if item["status"] != "approved":
            raise ValueError("Content must be approved before a publication request can be created.")
        key = (str(idempotency_key).strip() if idempotency_key else uuid.uuid4().hex)
        if not key or len(key) > 200:
            raise ValueError("Idempotency key must be between 1 and 200 characters.")

        # Reserve the idempotency key before creating an approval. This prevents
        # concurrent retries from creating multiple approval records.
        conn = get_connection()
        try:
            row = conn.execute(
                "INSERT INTO social_publication_attempts(social_content_id,user_id,platform,status,idempotency_key) "
                "VALUES (?,?,?,'approval_required',?) ON CONFLICT(user_id,idempotency_key) DO NOTHING RETURNING id",
                (content_id, user_id, item["platform"], key),
            ).fetchone()
            if not row:
                existing = conn.execute(
                    "SELECT id FROM social_publication_attempts WHERE user_id=? AND idempotency_key=?",
                    (user_id, key),
                ).fetchone()
                conn.commit()
                return self.get_attempt(user_id, existing["id"]) if existing else None
            attempt_id = row["id"]
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

        try:
            approval = self.approvals.create(
                user_id, "social.publish", f"social-content:{content_id}",
                payload={"operation": "social.publish", "content_id": content_id,
                         "publication_attempt_id": attempt_id, "platform": item["platform"],
                         "idempotency_key": key},
            )
            conn = get_connection()
            try:
                conn.execute(
                    "UPDATE social_publication_attempts SET approval_id=?,updated_at=CURRENT_TIMESTAMP "
                    "WHERE id=? AND user_id=? AND approval_id IS NULL",
                    (approval["id"], attempt_id, user_id),
                )
                conn.commit()
            finally:
                conn.close()
        except Exception:
            self._update_attempt(user_id, attempt_id, "failed", error_code="approval_creation_failed",
                                 result={"message": "Approval could not be created; no publication was attempted."})
            raise
        return self.get_attempt(user_id, attempt_id)

    def execute_approved(self, user_id, attempt_id):
        attempt = self.get_attempt(user_id, attempt_id)
        if not attempt:
            return None
        approval = self.approvals.get_for_user(attempt["approval_id"], user_id)
        if not approval or approval.get("status") != "approved":
            raise ValueError("Publication approval has not been granted.")
        item = self.content.get(user_id, attempt["social_content_id"])
        if not item or item.get("status") != "approved":
            raise ValueError("Approved source content is no longer available.")
        adapter = self.publishers.get(attempt["platform"])
        if not adapter:
            self._update_attempt(user_id, attempt_id, "failed",
                                 error_code="publisher_not_configured",
                                 result={"message": "No trusted publishing adapter is configured for this platform."})
            return self.get_attempt(user_id, attempt_id)

        # The provider adapter must implement its own idempotency semantics.
        self._update_attempt(user_id, attempt_id, "publishing")
        try:
            result = adapter.publish(item, attempt["idempotency_key"])
            if not isinstance(result, dict) or not result.get("external_post_id"):
                self._update_attempt(user_id, attempt_id, "failed",
                                     error_code="invalid_provider_result",
                                     result={"message": "Publisher returned no verified external post identifier."})
            else:
                self._update_attempt(user_id, attempt_id, "published",
                                     external_post_id=str(result["external_post_id"])[:500],
                                     result={"provider": result.get("provider"), "published": True})
        except Exception as exc:
            self._update_attempt(user_id, attempt_id, "failed",
                                 error_code=type(exc).__name__[:100],
                                 result={"message": "Publisher failed; verify provider state before retrying."})
        return self.get_attempt(user_id, attempt_id)

    def list_for_user(self, user_id, limit=30):
        conn = get_connection()
        try:
            rows = conn.execute(
                "SELECT id,social_content_id,platform,status,idempotency_key,approval_id,external_post_id,"
                "result_json,error_code,created_at,updated_at FROM social_publication_attempts "
                "WHERE user_id=? ORDER BY created_at DESC,id DESC LIMIT ?",
                (user_id, max(1, min(100, int(limit)))),
            ).fetchall()
            return [self._decode(row) for row in rows]
        finally:
            conn.close()

    def get_attempt(self, user_id, attempt_id):
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT id,social_content_id,platform,status,idempotency_key,approval_id,external_post_id,"
                "result_json,error_code,created_at,updated_at FROM social_publication_attempts "
                "WHERE id=? AND user_id=?",
                (attempt_id, user_id),
            ).fetchone()
            return self._decode(row) if row else None
        finally:
            conn.close()

    def _update_attempt(self, user_id, attempt_id, status, error_code=None, external_post_id=None, result=None):
        conn = get_connection()
        try:
            conn.execute(
                "UPDATE social_publication_attempts SET status=?,error_code=?,external_post_id=?,result_json=?,"
                "updated_at=CURRENT_TIMESTAMP WHERE id=? AND user_id=?",
                (status, error_code, external_post_id,
                 json.dumps(result or {}, ensure_ascii=False), attempt_id, user_id),
            )
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def _decode(row):
        item = dict(row)
        try:
            item["result"] = json.loads(item.pop("result_json") or "{}")
        except (TypeError, json.JSONDecodeError):
            item["result"] = {}
            item.pop("result_json", None)
        return item
