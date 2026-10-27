from tests.base import SmartBethGTestCase
from services.health_service import check_database, check_providers, check_background_worker
from services.operations_service import OperationsService


class TestHealthChecks(SmartBethGTestCase):
    def test_database_check_ok_when_reachable(self):
        result = check_database()
        self.assertEqual(result["status"], "ok")

    def test_provider_check_not_configured_when_no_keys(self):
        result = check_providers()
        self.assertEqual(result["status"], "not_configured")
        self.assertEqual(result["available"], [])
        self.assertIsNone(result["default"])

    def test_background_worker_uses_persisted_liveness_heartbeat(self):
        result = check_background_worker()
        self.assertIn(result["status"], {"ok", "not_running", "unknown"})
        self.assertIn("healthy_workers", result)

    def test_background_worker_reports_healthy_after_heartbeat(self):
        OperationsService().heartbeat_worker("health-test-worker", "healthy", {"test": True})
        result = check_background_worker()
        self.assertEqual(result["status"], "ok")
        self.assertGreaterEqual(result["healthy_workers"], 1)
