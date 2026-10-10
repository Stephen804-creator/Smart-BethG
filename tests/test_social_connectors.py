import unittest
from connectors.social import ConnectorNotConfigured, SocialConnectorRegistry


class TestSocialConnectorRegistry(unittest.TestCase):
    def test_catalog_does_not_claim_unimplemented_connectors_are_ready(self):
        catalog = SocialConnectorRegistry().catalog()
        self.assertTrue({"facebook", "instagram", "youtube", "linkedin", "x"}.issubset(
            {item["platform"] for item in catalog}
        ))
        self.assertTrue(all(item["status"] == "planned" for item in catalog))

    def test_missing_adapter_fails_closed(self):
        with self.assertRaises(ConnectorNotConfigured):
            SocialConnectorRegistry().get_publisher("facebook")


if __name__ == "__main__":
    unittest.main()
