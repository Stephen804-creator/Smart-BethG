import shutil
import tempfile

from fastapi.testclient import TestClient

import config
from database import get_connection
from main_fastapi import create_app
from services.auth_service import create_user
from services.approval_service import ApprovalService
from services.tool_service import ToolService
from tests.base import SmartBethGTestCase


class TestApprovalRouteExecution(SmartBethGTestCase):
    def setUp(self):
        super().setUp()
        self._projects_root = tempfile.mkdtemp(prefix="sbg_approval_route_projects_")
        self._old_projects_root = config.STORAGE_DIRS["projects"]
        config.STORAGE_DIRS["projects"] = self._projects_root
        self.user = create_user("approval-route-admin", "password123")
        conn = get_connection()
        try:
            conn.execute("UPDATE users SET role='admin' WHERE id=?", (self.user["id"],))
            conn.commit()
        finally:
            conn.close()
        self.client = TestClient(create_app())

    def tearDown(self):
        config.STORAGE_DIRS["projects"] = self._old_projects_root
        shutil.rmtree(self._projects_root, ignore_errors=True)
        super().tearDown()

    def _login(self):
        csrf = self.client.get("/auth/csrf").json()["csrf_token"]
        response = self.client.post(
            "/auth/login",
            headers={"X-CSRF-Token": csrf},
            json={"username": "approval-route-admin", "password": "password123"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        return self.client.get("/auth/csrf").json()["csrf_token"]

    def _create_legacy_approval(self):
        return ApprovalService().create(
            self.user["id"], "git.write", "workspace:demo",
            payload={"workspace": "demo", "kwargs": {"operation": "commit"}, "request_id": "test"},
        )

    def test_direct_tool_requests_cannot_create_approvals(self):
        result = ToolService().execute(
            {"id": self.user["id"], "role": "admin"},
            "git.write", workspace="demo", operation="commit",
        )
        self.assertEqual(result["status"], "unavailable")
        self.assertTrue(result["connector_required"])
        self.assertEqual(ApprovalService().list_pending(self.user["id"]), [])

    def test_positive_approval_cannot_execute_a_legacy_host_operation(self):
        csrf = self._login()
        approval = self._create_legacy_approval()
        response = self.client.post(
            f"/approvals/{approval['id']}",
            headers={"X-CSRF-Token": csrf},
            json={"approved": True},
        )
        self.assertEqual(response.status_code, 410, response.text)
        self.assertEqual(ApprovalService().get_for_user(approval["id"], self.user["id"])["status"], "pending")

    def test_rejection_remains_available_for_legacy_pending_approvals(self):
        csrf = self._login()
        approval = self._create_legacy_approval()
        response = self.client.post(
            f"/approvals/{approval['id']}",
            headers={"X-CSRF-Token": csrf},
            json={"approved": False},
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["approval"]["status"], "rejected")
        self.assertIsNone(response.json()["execution"])
