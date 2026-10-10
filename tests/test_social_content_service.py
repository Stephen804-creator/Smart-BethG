from tests.base import SmartBethGTestCase
from services.auth_service import create_user
from services.social_content_service import SocialContentService


class TestSocialContentService(SmartBethGTestCase):
    def setUp(self):
        super().setUp()
        self.owner = create_user("social-owner", "password123")
        self.other = create_user("social-other", "password123")
        self.service = SocialContentService()

    def test_draft_versioning_and_review_flow(self):
        item = self.service.create(self.owner["id"], "youtube", "AI safety", "A short draft", ["AI", "#Safety"])
        self.assertEqual(item["status"], "draft")
        self.assertEqual(item["hashtags"], ["AI", "Safety"])
        reviewed = self.service.transition(self.owner["id"], item["id"], "in_review")
        self.assertEqual(reviewed["status"], "in_review")
        approved = self.service.transition(self.owner["id"], item["id"], "approved")
        self.assertEqual(approved["status"], "approved")
        with self.assertRaises(ValueError):
            self.service.update(self.owner["id"], item["id"], {"content": "changed"})
        back_to_review = self.service.transition(self.owner["id"], item["id"], "in_review")
        updated = self.service.update(self.owner["id"], item["id"], {"content": "new draft"})
        self.assertEqual(updated["version"], 2)
        self.assertEqual(updated["status"], "draft")
        self.assertEqual(len(updated["versions"]), 2)

    def test_social_content_is_owner_scoped(self):
        item = self.service.create(self.owner["id"], "facebook", "Private", "Only my account")
        self.assertIsNone(self.service.get(self.other["id"], item["id"]))
        self.assertEqual(self.service.list_for_user(self.other["id"]), [])

    def test_publishing_is_not_faked(self):
        item = self.service.create(self.owner["id"], "blog", "Draft", "Not published")
        with self.assertRaises(ValueError):
            self.service.transition(self.owner["id"], item["id"], "published")


if __name__ == "__main__":
    import unittest
    unittest.main()
