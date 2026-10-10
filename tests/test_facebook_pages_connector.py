import unittest
from unittest.mock import Mock, patch

from connectors.facebook_pages import FacebookPagesPublisher
from connectors.social import ConnectorActionRejected


class FakeVault:
    def resolve(self, reference, user_id, provider):
        assert reference == "vault:page-credential"
        assert user_id == 7
        assert provider == "meta"
        return "mock-page-access-token"


class TestFacebookPagesPublisher(unittest.TestCase):
    def setUp(self):
        self.publisher = FacebookPagesPublisher(vault=FakeVault(), api_version="v26.0")

    @patch("connectors.facebook_pages.requests.post")
    def test_publishes_text_and_returns_provider_id(self, post):
        response = Mock()
        response.status_code = 200
        response.json.return_value = {"id": "page_123_post_456"}
        response.raise_for_status.return_value = None
        post.return_value = response
        result = self.publisher.publish(
            account={
                "user_id": 7, "external_account_id": "page_123",
                "credential_ref": "vault:page-credential",
            },
            content={
                "title": "Useful idea", "content": "Explain the concept simply.",
                "hashtags": ["AI", "learning!"],
            },
            idempotency_key="test-idempotency-key",
        )
        self.assertEqual(result["external_post_id"], "page_123_post_456")
        args, kwargs = post.call_args
        self.assertEqual(args[0], "https://graph.facebook.com/v26.0/page_123/feed")
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer mock-page-access-token")
        self.assertIn("Useful idea", kwargs["data"]["message"])
        self.assertIn("#AI", kwargs["data"]["message"])
        self.assertIn("#learning", kwargs["data"]["message"])

    @patch("connectors.facebook_pages.requests.post")
    def test_provider_permission_rejection_is_not_reported_as_success(self, post):
        response = Mock()
        response.status_code = 403
        post.return_value = response
        with self.assertRaisesRegex(ConnectorActionRejected, "HTTP 403"):
            self.publisher.publish(
                account={
                    "user_id": 7, "external_account_id": "page_123",
                    "credential_ref": "vault:page-credential",
                },
                content={"title": "Title", "content": "Body", "hashtags": []},
                idempotency_key="test-idempotency-key",
            )

    @patch("connectors.facebook_pages.requests.post")
    def test_missing_provider_post_id_is_not_reported_as_success(self, post):
        response = Mock()
        response.status_code = 200
        response.json.return_value = {"success": True}
        response.raise_for_status.return_value = None
        post.return_value = response
        with self.assertRaisesRegex(RuntimeError, "no post ID"):
            self.publisher.publish(
                account={
                    "user_id": 7, "external_account_id": "page_123",
                    "credential_ref": "vault:page-credential",
                },
                content={"title": "Title", "content": "Body", "hashtags": []},
                idempotency_key="test-idempotency-key",
            )


if __name__ == "__main__":
    unittest.main()
