from tests.base import SmartBethGTestCase
from services.auth_service import create_user
from services.connector_service import ConnectorInstallationService, ConnectorRegistry
from services.connector_action_service import ConnectorActionService
from services.connector_secrets import ConnectorSecretStore
from services.connector_oauth_service import ConnectorOAuthService
from database import get_connection

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

    def test_connector_credentials_are_encrypted_at_rest(self):
        installed=self.installations.install(self.owner["id"],"github",permissions=["github.issues.list"])
        store=ConnectorSecretStore()
        store.put(installed["id"],{"access_token":"token-that-must-not-be-plaintext"},"example",["repo"])
        conn=get_connection()
        try:
            row=conn.execute("SELECT encrypted_payload FROM connector_credentials WHERE installation_id=?",(installed["id"],)).fetchone()
        finally:
            conn.close()
        self.assertNotIn("token-that-must-not-be-plaintext",row["encrypted_payload"])
        self.assertEqual(store.get(installed["id"])["credentials"]["access_token"],"token-that-must-not-be-plaintext")
        store.delete(installed["id"])

    def test_oauth_start_fails_closed_when_provider_app_is_not_configured(self):
        service=ConnectorOAuthService()
        if service.configured("github"):
            self.skipTest("GitHub OAuth credentials are configured in this environment.")
        with self.assertRaises(RuntimeError):
            service.start(self.owner["id"],999,"github","https://example.test/callback")

    def test_catalog_separates_adapter_code_from_oauth_configuration(self):
        catalog={item["key"]:item for item in ConnectorRegistry().catalog()}
        self.assertTrue(catalog["github"]["adapter_available"])
        self.assertTrue(catalog["google_drive"]["adapter_available"])
        self.assertTrue(catalog["slack"]["adapter_available"])
        self.assertTrue(catalog["smartbethg"]["adapter_available"])
        # Adapter code exists, but external OAuth is not assumed configured in tests.
        self.assertFalse(catalog["github"]["oauth_configured"])
