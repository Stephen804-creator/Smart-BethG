import os
import unittest
from unittest.mock import patch

from cryptography.fernet import Fernet
from connectors.social import ConnectorNotConfigured, SocialConnectorRegistry
from routes.connectors import _meta_ready_for_oauth


class TestSocialConnectorRegistry(unittest.TestCase):
    def test_catalog_does_not_claim_unimplemented_connectors_are_ready(self):
        catalog = SocialConnectorRegistry().catalog()
        self.assertTrue({"facebook", "instagram", "youtube", "linkedin", "x"}.issubset(
            {item["platform"] for item in catalog}
        ))
        self.assertTrue(all(item["status"] == "planned" for item in catalog))

    def test_facebook_publisher_requires_explicit_operator_enablement(self):
        env = {
            "SMART_BETHG_META_PUBLISHING_ENABLED": "true",
            "SMART_BETHG_META_APP_ID": "test-app-id",
            "SMART_BETHG_META_APP_SECRET": "test-app-secret",
            "SMART_BETHG_META_REDIRECT_URI": "https://example.test/connectors/meta/callback",
            "SMART_BETHG_TOKEN_ENCRYPTION_KEY": Fernet.generate_key().decode(),
        }
        with patch.dict(os.environ, env, clear=False):
            registry = SocialConnectorRegistry()
            facebook = next(item for item in registry.catalog() if item["platform"] == "facebook")
            self.assertEqual(facebook["status"], "ready")
            self.assertTrue(registry.get_publisher("facebook"))

    def test_meta_oauth_requires_registered_callback_and_safe_scheme(self):
        base = {
            "app_id": "test-app",
            "app_secret": "test-secret",
            "api_version": "v26.0",
            "redirect_uri": "https://smartbethg.example/connectors/meta/callback",
        }
        self.assertTrue(_meta_ready_for_oauth(base))
        invalid_path = dict(base, redirect_uri="https://smartbethg.example/not-the-callback")
        self.assertFalse(_meta_ready_for_oauth(invalid_path))
        remote_http = dict(base, redirect_uri="http://smartbethg.example/connectors/meta/callback")
        self.assertFalse(_meta_ready_for_oauth(remote_http))
        invalid_version = dict(base, api_version="latest")
        self.assertFalse(_meta_ready_for_oauth(invalid_version))

    def test_missing_adapter_fails_closed(self):
        with self.assertRaises(ConnectorNotConfigured):
            SocialConnectorRegistry().get_publisher("facebook")


if __name__ == "__main__":
    unittest.main()
