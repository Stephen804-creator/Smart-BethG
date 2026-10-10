import unittest
from connectors.social import ConnectorNotConfigured, SocialConnectorRegistry


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

    def test_missing_adapter_fails_closed(self):
        with self.assertRaises(ConnectorNotConfigured):
            SocialConnectorRegistry().get_publisher("facebook")


if __name__ == "__main__":
    unittest.main()
