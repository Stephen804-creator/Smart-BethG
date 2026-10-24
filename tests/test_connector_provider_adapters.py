import unittest
from unittest.mock import Mock, patch
from services.connector_provider_adapters import ProviderAdapter

class FakeSecrets:
    def __init__(self, provider="github"):
        self.value = {"credentials":{"access_token":"test-token"},"provider_account":"test","scopes":[],"expires_at":None}
    def get(self, installation_id):
        return self.value
    def put(self, installation_id, credentials, provider_account=None, scopes=None, expires_at=None):
        self.value={"credentials":credentials,"provider_account":provider_account,"scopes":scopes or [],"expires_at":expires_at}

class TestProviderAdapters(unittest.TestCase):
    def test_github_issues_list_uses_authorized_token_and_bounded_page_size(self):
        response=Mock()
        response.json.return_value=[{"number":3,"title":"Bug","state":"open","html_url":"https://github.com/a/b/issues/3"}]
        response.raise_for_status.return_value=None
        with patch("services.connector_provider_adapters.httpx.get",return_value=response) as get:
            result=ProviderAdapter("github",FakeSecrets()).execute(
                "issues.list",{"repository":"a/b","limit":999},{"installation_id":4})
        self.assertTrue(result["success"])
        self.assertEqual(result["data"][0]["number"],3)
        self.assertEqual(get.call_args.kwargs["params"]["per_page"],50)
        self.assertEqual(get.call_args.kwargs["headers"]["Authorization"],"Bearer test-token")

    def test_github_create_adds_idempotency_marker(self):
        response=Mock()
        response.json.return_value={"number":5,"title":"Issue","html_url":"https://github.com/a/b/issues/5"}
        response.raise_for_status.return_value=None
        with patch("services.connector_provider_adapters.httpx.post",return_value=response) as post:
            result=ProviderAdapter("github",FakeSecrets()).execute(
                "issues.create",{"repository":"a/b","title":"Issue","body":"Body"},
                {"installation_id":4,"idempotency_key":"stable-key"})
        self.assertTrue(result["success"])
        self.assertIn("smart-bethg-idempotency:stable-key",post.call_args.kwargs["json"]["body"])

    def test_slack_api_rejection_is_not_reported_as_success(self):
        response=Mock()
        response.json.return_value={"ok":False,"error":"channel_not_found"}
        response.raise_for_status.return_value=None
        with patch("services.connector_provider_adapters.httpx.post",return_value=response):
            result=ProviderAdapter("slack",FakeSecrets()).execute(
                "messages.send",{"channel":"C123","text":"Hello"},{"installation_id":4})
        self.assertFalse(result["success"])
        self.assertEqual(result["status"],"provider_error")

    def test_unknown_action_fails_closed(self):
        result=ProviderAdapter("github",FakeSecrets()).execute(
            "shell.run",{},{"installation_id":4})
        self.assertFalse(result["success"])
        self.assertEqual(result["status"],"provider_error")

if __name__=="__main__":
    unittest.main()
