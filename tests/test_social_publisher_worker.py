from datetime import datetime, timedelta, timezone
import json

from database import get_connection
from services.auth_service import create_user
from services.social_campaign_service import SocialCampaignService
from tests.base import SmartBethGTestCase
from workers.social_publisher import SocialPublisherWorker


class FakePublisher:
    def __init__(self, outcome=None, error=None):
        self.calls = []
        self.outcome = outcome or {"external_post_id": "provider-post-123"}
        self.error = error

    def publish(self, *, account, content, idempotency_key):
        self.calls.append((account, content, idempotency_key))
        if self.error:
            raise self.error
        return self.outcome


class FakeRegistry:
    def __init__(self, publisher=None, error=None):
        self.publisher = publisher
        self.error = error

    def get_publisher(self, platform):
        if self.error:
            raise self.error
        return self.publisher


class TestSocialPublisherWorker(SmartBethGTestCase):
    def setUp(self):
        super().setUp()
        self.user = create_user("publisher-worker-user", "password123")
        self.service = SocialCampaignService()
        start = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat(timespec="seconds")
        end = (datetime.now(timezone.utc) + timedelta(days=5)).isoformat(timespec="seconds")
        self.campaign = self.service.create(
            self.user["id"], name="Worker test", objective="Test safe publishing",
            platforms=["facebook"], timezone_name="Africa/Lagos", start_at=start, end_at=end,
            daily_post_limit=2,
        )
        self.service.add_posts(self.user["id"], self.campaign["id"], [{
            "platform": "facebook", "title": "Worker test post", "content": "A test post",
            "scheduled_at": start,
        }])
        conn = get_connection()
        try:
            conn.execute(
                "UPDATE social_campaigns SET status='active' WHERE id=? AND user_id=?",
                (self.campaign["id"], self.user["id"]),
            )
            conn.execute(
                "UPDATE social_content SET status='approved' WHERE campaign_id=? AND user_id=?",
                (self.campaign["id"], self.user["id"]),
            )
            conn.execute(
                "INSERT INTO social_connections(user_id, platform, external_account_id, display_name, "
                "credential_ref, scopes_json, status, connected_at) "
                "VALUES (?, 'facebook', 'page-test-1', 'Test Page', 'secret-ref:test-account', "
                "'[\"pages_manage_posts\"]', 'active', CURRENT_TIMESTAMP)",
                (self.user["id"],),
            )
            connection = conn.execute(
                "SELECT id FROM social_connections WHERE user_id=? AND platform='facebook'",
                (self.user["id"],),
            ).fetchone()
            conn.execute(
                "UPDATE social_publish_jobs SET status='queued', connection_id=? "
                "WHERE campaign_id=? AND user_id=?",
                (connection["id"], self.campaign["id"], self.user["id"]),
            )
            conn.commit()
        finally:
            conn.close()

    def test_successful_publish_is_persisted_and_not_replayed(self):
        publisher = FakePublisher()
        worker = SocialPublisherWorker(registry=FakeRegistry(publisher), batch_size=5)
        result = worker.run_once()
        self.assertEqual(result, [{"job_id": 1, "status": "published"}])
        self.assertEqual(len(publisher.calls), 1)
        self.assertEqual(worker.run_once(), [])
        conn = get_connection()
        try:
            job = conn.execute(
                "SELECT status, external_post_id FROM social_publish_jobs WHERE campaign_id=?",
                (self.campaign["id"],),
            ).fetchone()
            post = conn.execute(
                "SELECT status, external_post_id FROM social_content WHERE campaign_id=?",
                (self.campaign["id"],),
            ).fetchone()
            self.assertEqual(job["status"], "published")
            self.assertEqual(job["external_post_id"], "provider-post-123")
            self.assertEqual(post["status"], "published")
            self.assertEqual(post["external_post_id"], "provider-post-123")
        finally:
            conn.close()

    def test_autonomous_publish_is_blocked_when_scope_does_not_cover_platform(self):
        conn = get_connection()
        try:
            conn.execute(
                "UPDATE social_campaigns SET autonomy_mode='auto_publish_after_campaign_approval', "
                "autopublish_authorized_at=CURRENT_TIMESTAMP, authorization_scope_json=? "
                "WHERE id=? AND user_id=?",
                (json.dumps({
                    "platforms": [],
                    "start_at": self.campaign["start_at"],
                    "end_at": self.campaign["end_at"],
                    "daily_post_limit": 2,
                }), self.campaign["id"], self.user["id"]),
            )
            conn.commit()
        finally:
            conn.close()

        worker = SocialPublisherWorker(registry=FakeRegistry(FakePublisher()))
        result = worker.run_once()
        self.assertEqual(result[0]["status"], "blocked")
        conn = get_connection()
        try:
            job = conn.execute(
                "SELECT status, error_code FROM social_publish_jobs WHERE campaign_id=?",
                (self.campaign["id"],),
            ).fetchone()
            self.assertEqual(job["status"], "blocked")
            self.assertEqual(job["error_code"], "authorization_scope_invalid")
        finally:
            conn.close()

    def test_missing_connector_blocks_without_fake_success(self):
        from connectors.social import ConnectorNotConfigured
        worker = SocialPublisherWorker(registry=FakeRegistry(error=ConnectorNotConfigured("not ready")))
        result = worker.run_once()
        self.assertEqual(result[0]["status"], "blocked")
        conn = get_connection()
        try:
            job = conn.execute(
                "SELECT status, error_code FROM social_publish_jobs WHERE campaign_id=?",
                (self.campaign["id"],),
            ).fetchone()
            self.assertEqual(job["status"], "blocked")
            self.assertEqual(job["error_code"], "connector_not_configured")
        finally:
            conn.close()

    def test_unknown_provider_outcome_is_indeterminate_not_retried(self):
        worker = SocialPublisherWorker(registry=FakeRegistry(FakePublisher(error=RuntimeError("timeout"))))
        result = worker.run_once()
        self.assertEqual(result[0]["status"], "indeterminate")
        self.assertEqual(worker.run_once(), [])
        conn = get_connection()
        try:
            job = conn.execute(
                "SELECT status, error_code FROM social_publish_jobs WHERE campaign_id=?",
                (self.campaign["id"],),
            ).fetchone()
            self.assertEqual(job["status"], "indeterminate")
            self.assertEqual(job["error_code"], "provider_outcome_unknown")
        finally:
            conn.close()


if __name__ == "__main__":
    import unittest
    unittest.main()
