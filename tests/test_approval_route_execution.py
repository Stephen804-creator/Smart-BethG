import os
import shutil
import subprocess
import tempfile

from fastapi.testclient import TestClient

import config
from database import get_connection
from main_fastapi import create_app
from services.auth_service import create_user
from services.tool_service import ToolService, resolve_workspace_root
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

    def test_approval_route_executes_saved_git_operation_once(self):
        csrf = self.client.get("/auth/csrf").json()["csrf_token"]
        login = self.client.post(
            "/auth/login",
            headers={"X-CSRF-Token": csrf},
            json={"username": "approval-route-admin", "password": "password123"},
        )
        self.assertEqual(login.status_code, 200, login.text)
        csrf = self.client.get("/auth/csrf").json()["csrf_token"]

        workspace = "route-approval-repo"
        root = resolve_workspace_root(self.user["id"], workspace)
        subprocess.run(["git", "init"], cwd=root, capture_output=True, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=root, check=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
        with open(os.path.join(root, "approval.txt"), "w", encoding="utf-8") as handle:
            handle.write("only execute after approval")
        subprocess.run(["git", "add", "-A"], cwd=root, check=True)

        pending = ToolService().execute(
            {"id": self.user["id"], "role": "admin"},
            "git.write",
            workspace=workspace,
            operation="commit",
            message="executed from approval route",
        )
        self.assertEqual(pending["status"], "approval_required")

        response = self.client.post(
            f"/approvals/{pending['approval_id']}",
            headers={"X-CSRF-Token": csrf},
            json={"approved": True},
        )
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertTrue(payload["execution"]["success"])
        self.assertEqual(payload["execution"]["execution_status"], "completed")

        log = subprocess.run(
            ["git", "log", "-1", "--pretty=%s"], cwd=root, capture_output=True, text=True, check=True
        )
        self.assertEqual(log.stdout.strip(), "executed from approval route")

        duplicate = self.client.post(
            f"/approvals/{pending['approval_id']}",
            headers={"X-CSRF-Token": csrf},
            json={"approved": True},
        )
        self.assertEqual(duplicate.status_code, 409)
        count = subprocess.run(
            ["git", "rev-list", "--count", "HEAD"], cwd=root, capture_output=True, text=True, check=True
        )
        self.assertEqual(count.stdout.strip(), "1")


    def test_approved_but_not_yet_claimed_operation_resumes_on_retry(self):
        csrf = self.client.get("/auth/csrf").json()["csrf_token"]
        login = self.client.post(
            "/auth/login",
            headers={"X-CSRF-Token": csrf},
            json={"username": "approval-route-admin", "password": "password123"},
        )
        self.assertEqual(login.status_code, 200, login.text)
        csrf = self.client.get("/auth/csrf").json()["csrf_token"]

        workspace = "recovery-approval-repo"
        root = resolve_workspace_root(self.user["id"], workspace)
        subprocess.run(["git", "init"], cwd=root, capture_output=True, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=root, check=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
        with open(os.path.join(root, "recovery.txt"), "w", encoding="utf-8") as handle:
            handle.write("resume only after approval")

        pending = ToolService().execute(
            {"id": self.user["id"], "role": "admin"},
            "git.write",
            workspace=workspace,
            operation="commit",
            message="resumed after approval decision",
        )
        self.assertEqual(pending["status"], "approval_required")

        # Simulate interruption after decision commit but before execution claim.
        from services.approval_service import ApprovalService
        ApprovalService().decide(pending["approval_id"], self.user["id"], True)

        response = self.client.post(
            f"/approvals/{pending['approval_id']}",
            headers={"X-CSRF-Token": csrf},
            json={"approved": True},
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(response.json()["execution"]["success"])

        count = subprocess.run(
            ["git", "rev-list", "--count", "HEAD"], cwd=root,
            capture_output=True, text=True, check=True
        )
        self.assertEqual(count.stdout.strip(), "1")


    def test_rejected_operation_does_not_run(self):
        csrf = self.client.get("/auth/csrf").json()["csrf_token"]
        login = self.client.post(
            "/auth/login",
            headers={"X-CSRF-Token": csrf},
            json={"username": "approval-route-admin", "password": "password123"},
        )
        self.assertEqual(login.status_code, 200, login.text)
        csrf = self.client.get("/auth/csrf").json()["csrf_token"]

        workspace = "rejected-approval-repo"
        root = resolve_workspace_root(self.user["id"], workspace)
        subprocess.run(["git", "init"], cwd=root, capture_output=True, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=root, check=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
        with open(os.path.join(root, "rejected.txt"), "w", encoding="utf-8") as handle:
            handle.write("this must not be committed")
        subprocess.run(["git", "add", "-A"], cwd=root, check=True)

        pending = ToolService().execute(
            {"id": self.user["id"], "role": "admin"},
            "git.write",
            workspace=workspace,
            operation="commit",
            message="must not execute after rejection",
        )
        self.assertEqual(pending["status"], "approval_required")

        response = self.client.post(
            f"/approvals/{pending['approval_id']}",
            headers={"X-CSRF-Token": csrf},
            json={"approved": False},
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["approval"]["status"], "rejected")
        self.assertIsNone(response.json()["execution"])
        self.assertFalse(os.path.exists(os.path.join(root, ".git", "refs", "heads", "master")))
        self.assertFalse(os.path.exists(os.path.join(root, ".git", "refs", "heads", "main")))

        retry = self.client.post(
            f"/approvals/{pending['approval_id']}",
            headers={"X-CSRF-Token": csrf},
            json={"approved": True},
        )
        self.assertEqual(retry.status_code, 409)


if __name__ == "__main__":
    import unittest
    unittest.main()
