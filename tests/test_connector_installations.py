from tests.base import SmartBethGTestCase
from services.auth_service import create_user
from services.connector_service import ConnectorInstallationService, ConnectorRegistry
from services.connector_action_service import ConnectorActionService

class TestConnectorInstallations(SmartBethGTestCase):
    def setUp(self):
        super().setUp()
        self.owner=create_user("connector-owner","password123")
        self.other=create_user("connector-other","password123")
        self.installations=ConnectorInstallationService()

    def test_installation_is_owner_scoped_and_does_not_expose_secret_reference(self):
        installed=self.installations.install(self.owner["id"],"smartbethg")
        self.assertEqual(installed["status"],"disconnected")
        self.assertIn("smartbethg.knowledge.search",installed["granted_permissions"])
        self.assertNotIn("credential_ref",installed)
        self.assertIsNone(self.installations.get_for_user(self.other["id"],installed["id"]))

    def test_builtin_knowledge_adapter_runs_read_only_search(self):
        installed=self.installations.install(self.owner["id"],"smartbethg")
        result=ConnectorActionService().request_action(
            self.owner["id"],installed["id"],"knowledge.search",{"query":"not-yet-indexed phrase","limit":2}
        )
        self.assertEqual(result["status"],"completed")
        self.assertTrue(result["result"]["success"])
        self.assertEqual(result["result"]["results"],[])

    def test_catalog_does_not_claim_external_adapters_are_live(self):
        catalog={item["key"]:item for item in ConnectorRegistry().catalog()}
        self.assertTrue(catalog["github"]["adapter_available"])
        self.assertTrue(catalog["google_drive"]["adapter_available"])
        self.assertTrue(catalog["slack"]["adapter_available"])
        self.assertTrue(catalog["smartbethg"]["adapter_available"])
        # Adapter code exists, but external OAuth is not assumed configured in tests.
        self.assertFalse(catalog["github"]["oauth_configured"])
