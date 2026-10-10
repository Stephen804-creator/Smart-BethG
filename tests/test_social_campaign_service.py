from tests.base import SmartBethGTestCase
from services.auth_service import create_user
from services.social_campaign_service import SocialCampaignService
from services.social_content_service import SocialContentService
from unittest.mock import patch


class TestSocialCampaignService(SmartBethGTestCase):
    def setUp(self):
        super().setUp()
        self.owner = create_user("campaign-owner", "password123")
        self.other = create_user("campaign-other", "password123")
        self.service = SocialCampaignService()

    def create_campaign(self, owner=None, **overrides):
        values = {
            "name": "Thirty-day launch",
            "objective": "Educate the audience and grow reach",
            "platforms": ["facebook", "linkedin"],
            "timezone_name": "Africa/Lagos",
            "start_at": "2026-10-12T08:00:00+01:00",
            "end_at": "2026-11-12T23:00:00+01:00",
            "cadence": {"days": ["mon", "wed", "fri"], "local_time": "08:00"},
            "daily_post_limit": 2,
        }
        values.update(overrides)
        return self.service.create((owner or self.owner)["id"], **values)

    def test_campaign_round_trip_and_owner_isolation(self):
        campaign = self.create_campaign()
        self.assertEqual(campaign["platforms"], ["facebook", "linkedin"])
        self.assertEqual(campaign["timezone"], "Africa/Lagos")
        self.assertIsNone(self.service.get(self.other["id"], campaign["id"]))
        self.assertEqual(self.service.list_for_user(self.other["id"]), [])

    def test_requires_timezone_aware_timestamps(self):
        with self.assertRaisesRegex(ValueError, "timezone offset"):
            self.create_campaign(start_at="2026-10-12T08:00:00")

    def test_autonomous_publishing_requires_explicit_authorization(self):
        with self.assertRaisesRegex(ValueError, "explicit campaign-level authorization"):
            self.create_campaign(autonomy_mode="auto_publish_after_campaign_approval")
        campaign = self.create_campaign(
            name="Authorized campaign",
            autonomy_mode="auto_publish_after_campaign_approval",
            auto_publish_authorized=True,
        )
        self.assertEqual(campaign["autonomy_mode"], "auto_publish_after_campaign_approval")

    def test_autonomous_campaign_requires_a_bounded_authorization_window(self):
        with self.assertRaisesRegex(ValueError, "explicit campaign end date"):
            self.create_campaign(
                autonomy_mode="auto_publish_after_campaign_approval",
                auto_publish_authorized=True,
                end_at=None,
            )
        with self.assertRaisesRegex(ValueError, "90-day authorization window"):
            self.create_campaign(
                autonomy_mode="auto_publish_after_campaign_approval",
                auto_publish_authorized=True,
                end_at="2027-02-01T23:00:00+01:00",
            )

    def test_add_batch_creates_versioned_posts_and_durable_jobs(self):
        campaign = self.create_campaign()
        result = self.service.add_posts(self.owner["id"], campaign["id"], [
            {"platform": "facebook", "title": "Day one", "content": "Useful content for day one.",
             "hashtags": ["learning"], "scheduled_at": "2026-10-12T08:00:00+01:00"},
            {"platform": "linkedin", "title": "Day two", "content": "Useful content for day two.",
             "hashtags": ["engineering"], "scheduled_at": "2026-10-13T08:00:00+01:00"},
        ])
        self.assertEqual(len(result["posts"]), 2)
        self.assertEqual(result["status"], "planned")
        import database
        conn = database.get_connection()
        try:
            jobs = conn.execute(
                "SELECT status, idempotency_key FROM social_publish_jobs WHERE user_id=? AND campaign_id=?",
                (self.owner["id"], campaign["id"]),
            ).fetchall()
            self.assertEqual(len(jobs), 2)
            self.assertTrue(all(row["status"] == "awaiting_approval" for row in jobs))
            self.assertEqual(len({row["idempotency_key"] for row in jobs}), 2)
        finally:
            conn.close()

    def test_daily_limit_is_enforced_atomically(self):
        campaign = self.create_campaign(daily_post_limit=1)
        posts = [
            {"platform": "facebook", "title": "A", "content": "Post A",
             "scheduled_at": "2026-10-12T08:00:00+01:00"},
            {"platform": "facebook", "title": "B", "content": "Post B",
             "scheduled_at": "2026-10-12T15:00:00+01:00"},
        ]
        with self.assertRaisesRegex(ValueError, "daily post limit"):
            self.service.add_posts(self.owner["id"], campaign["id"], posts)
        import database
        conn = database.get_connection()
        try:
            count = conn.execute(
                "SELECT COUNT(*) AS n FROM social_content WHERE user_id=? AND campaign_id=?",
                (self.owner["id"], campaign["id"]),
            ).fetchone()["n"]
            self.assertEqual(count, 0)
        finally:
            conn.close()

    def test_generate_plan_batches_ai_output_and_saves_only_after_validation(self):
        campaign = self.create_campaign(daily_post_limit=2)
        class FakeGenerator:
            def __init__(self):
                self.calls = 0
            def generate_task(self, user_id, prompt, selection=None):
                self.calls += 1
                count = 3 if self.calls == 1 else 1
                import json
                return {
                    "provider_configured": True,
                    "text": json.dumps([
                        {"title": f"Post {self.calls}-{i}", "content": f"Useful post {self.calls}-{i}",
                         "hashtags": ["education"]}
                        for i in range(count)
                    ]),
                }
        with patch("services.social_campaign_service.ChatService", FakeGenerator):
            result = self.service.generate_plan(self.owner["id"], campaign["id"], count=4)
        self.assertEqual(len(result["posts"]), 4)
        self.assertEqual(len({post["scheduled_at"] for post in result["posts"]}), 4)

    def test_invalid_ai_output_does_not_create_partial_campaign_posts(self):
        campaign = self.create_campaign()
        class FakeGenerator:
            def __init__(self):
                self.calls = 0
            def generate_task(self, user_id, prompt, selection=None):
                self.calls += 1
                if self.calls == 1:
                    return {"provider_configured": True, "text": '[{"title":"A","content":"A","hashtags":[]},{"title":"B","content":"B","hashtags":[]},{"title":"C","content":"C","hashtags":[]}]'}
                return {"provider_configured": True, "text": "not json"}
        with patch("services.social_campaign_service.ChatService", FakeGenerator):
            with self.assertRaisesRegex(ValueError, "valid JSON array"):
                self.service.generate_plan(self.owner["id"], campaign["id"], count=4)
        import database
        conn = database.get_connection()
        try:
            count = conn.execute(
                "SELECT COUNT(*) AS n FROM social_content WHERE user_id=? AND campaign_id=?",
                (self.owner["id"], campaign["id"]),
            ).fetchone()["n"]
            self.assertEqual(count, 0)
        finally:
            conn.close()

    def test_editing_campaign_post_invalidates_previous_approval(self):
        campaign = self.create_campaign()
        planned = self.service.add_posts(self.owner["id"], campaign["id"], [{
            "platform": "facebook", "title": "Original", "content": "Original content",
            "scheduled_at": "2026-10-12T08:00:00+01:00",
        }])
        post_id = planned["posts"][0]["id"]
        self.service.approve_post(self.owner["id"], campaign["id"], post_id)
        content_service = SocialContentService()
        content_service.transition(self.owner["id"], post_id, "in_review")
        edited = content_service.update(self.owner["id"], post_id, {"content": "Changed after approval"})
        self.assertEqual(edited["status"], "draft")
        campaign = self.service.get(self.owner["id"], campaign["id"])
        post = next(item for item in campaign["posts"] if item["id"] == post_id)
        self.assertEqual(post["publish_status"], "awaiting_approval")
        self.assertIsNone(post["publish_error_code"])
        reapproved = self.service.approve_post(self.owner["id"], campaign["id"], post_id)
        post = next(item for item in reapproved["posts"] if item["id"] == post_id)
        self.assertEqual(post["status"], "approved")
        self.assertEqual(post["publish_status"], "awaiting_connection")

    def test_campaign_posts_cannot_bypass_campaign_approval_route(self):
        campaign = self.create_campaign()
        planned = self.service.add_posts(self.owner["id"], campaign["id"], [{
            "platform": "facebook", "title": "Review", "content": "Needs campaign approval",
            "scheduled_at": "2026-10-12T08:00:00+01:00",
        }])
        content_service = SocialContentService()
        content_service.transition(self.owner["id"], planned["posts"][0]["id"], "in_review")
        with self.assertRaisesRegex(ValueError, "campaign approval endpoint"):
            content_service.transition(self.owner["id"], planned["posts"][0]["id"], "approved")

    def test_campaign_cannot_target_unselected_platform(self):
        campaign = self.create_campaign(platforms=["facebook"])
        with self.assertRaisesRegex(ValueError, "not part of this campaign"):
            self.service.add_posts(self.owner["id"], campaign["id"], [{
                "platform": "linkedin", "title": "Wrong platform", "content": "No",
                "scheduled_at": "2026-10-12T08:00:00+01:00",
            }])


if __name__ == "__main__":
    import unittest
    unittest.main()
