import os
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from fastapi import HTTPException

import config
import database
from main_fastapi import create_app
from services.approval_service import ApprovalService
from services.tool_service import resolve_workspace_root


class TestHttpSecurityBoundaries(unittest.TestCase):
    def test_approvals_endpoint_requires_authentication(self):
        client = TestClient(create_app())
        response = client.get("/approvals")
        self.assertEqual(response.status_code, 401)

    def test_chat_api_has_canonical_versioned_path(self):
        client = TestClient(create_app())
        canonical = client.get("/api/v1/chat/conversations")
        old_wart = client.get("/api/v1/api/chat/conversations")
        self.assertEqual(canonical.status_code, 401)
        self.assertEqual(old_wart.status_code, 404)

    def test_registration_can_be_closed_by_operator(self):
        with patch.object(config, "REGISTRATION_OPEN", False):
            client = TestClient(create_app())
            response = client.post(
                "/auth/register",
                json={"username": "closed-registration-test", "password": "not-a-real-password"},
            )
        self.assertEqual(response.status_code, 403)
        self.assertIn("closed", response.json()["error"]["message"].lower())

    def test_cors_preflight_accepts_only_configured_origin(self):
        with patch.object(config, "ALLOWED_ORIGINS", ["https://allowed.example"]):
            client = TestClient(create_app())
            allowed = client.options(
                "/auth/login",
                headers={
                    "Origin": "https://allowed.example",
                    "Access-Control-Request-Method": "POST",
                },
            )
            denied = client.options(
                "/auth/login",
                headers={
                    "Origin": "https://untrusted.example",
                    "Access-Control-Request-Method": "POST",
                },
            )

        self.assertEqual(allowed.headers.get("access-control-allow-origin"), "https://allowed.example")
        self.assertNotEqual(denied.headers.get("access-control-allow-origin"), "https://untrusted.example")


class TestApprovalService(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path_patch = patch.object(
            database, "DB_PATH", os.path.join(self.temp_dir.name, "test.db")
        )
        self.db_path_patch.start()
        database.initialize_database()
        self.service = ApprovalService()

    def tearDown(self):
        self.db_path_patch.stop()
        self.temp_dir.cleanup()

    def test_pending_approval_is_persisted_and_scoped_to_owner(self):
        created = self.service.create(10, "delete_file", "report.txt")
        self.assertEqual(created["status"], "pending")
        self.assertEqual(len(self.service.list_pending(10)), 1)
        self.assertEqual(self.service.list_pending(11), [])

    def test_other_user_cannot_decide_approval(self):
        created = self.service.create(10, "send_email", "recipient@example.test")
        with self.assertRaises(HTTPException) as caught:
            self.service.decide(created["id"], 11, True)
        self.assertEqual(caught.exception.status_code, 404)
        self.assertFalse(self.service.is_approved(created["id"]))

    def test_decision_is_persisted_and_cannot_be_changed(self):
        created = self.service.create(10, "publish_post", "draft-1")
        decided = self.service.decide(created["id"], 10, True)
        self.assertEqual(decided["status"], "approved")
        self.assertTrue(self.service.is_approved(created["id"]))
        with self.assertRaises(HTTPException) as caught:
            self.service.decide(created["id"], 10, False)
        self.assertEqual(caught.exception.status_code, 409)

    def test_missing_approval_returns_not_found(self):
        with self.assertRaises(HTTPException) as caught:
            self.service.decide("does-not-exist", 10, True)
        self.assertEqual(caught.exception.status_code, 404)


class TestWorkspaceIsolation(unittest.TestCase):
    def test_workspaces_are_isolated_by_authenticated_user(self):
        with tempfile.TemporaryDirectory() as root:
            with patch.dict(config.STORAGE_DIRS, {"projects": root}):
                user_one = resolve_workspace_root(101, "default")
                user_two = resolve_workspace_root(202, "default")
                self.assertNotEqual(user_one, user_two)
                self.assertTrue(user_one.startswith(os.path.join(root, "101")))
                self.assertTrue(user_two.startswith(os.path.join(root, "202")))

    def test_workspace_name_cannot_escape_user_root(self):
        with tempfile.TemporaryDirectory() as root:
            with patch.dict(config.STORAGE_DIRS, {"projects": root}):
                resolved = resolve_workspace_root(101, "../../another-user")
                self.assertTrue(resolved.startswith(os.path.join(root, "101")))
                self.assertNotIn("..", os.path.relpath(resolved, os.path.join(root, "101")))


if __name__ == "__main__":
    unittest.main()
