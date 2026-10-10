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
    def test_security_headers_are_present(self):
        client = TestClient(create_app())
        response = client.get("/health")
        self.assertEqual(response.headers.get("x-content-type-options"), "nosniff")
        self.assertEqual(response.headers.get("x-frame-options"), "DENY")
        self.assertEqual(response.headers.get("referrer-policy"), "strict-origin-when-cross-origin")
        csp = response.headers.get("content-security-policy-report-only", "")
        self.assertIn("default-src 'self'", csp)
        self.assertIn("object-src 'none'", csp)
        self.assertIn("frame-ancestors 'none'", csp)
        self.assertIn("script-src 'self'", csp)
        self.assertNotIn("'unsafe-eval'", csp)
        self.assertNotIn("Content-Security-Policy", response.headers)  # report-only rollout


    def test_all_state_changing_api_routes_require_csrf(self):
        import database
        from services.auth_service import create_user

        with tempfile.TemporaryDirectory() as temp_dir:
            old_db_path = database.DB_PATH
            old_database_url = config.DATABASE_URL
            database.DB_PATH = os.path.join(temp_dir, "csrf-test.db")
            config.DATABASE_URL = ""
            try:
                database.initialize_database()
                username = "csrf-boundary-test"
                user = create_user(username, "csrf-test-password")
                self.assertIsNotNone(user)
                client = TestClient(create_app())

                token = client.get("/auth/csrf").json()["csrf_token"]
                login = client.post(
                    "/auth/login",
                    headers={"X-CSRF-Token": token},
                    json={"username": username, "password": "csrf-test-password"},
                )
                self.assertEqual(login.status_code, 200, login.text)
                fresh_token = client.get("/auth/csrf").json()["csrf_token"]

                blocked = client.post(
                    "/api/v1/projects",
                    json={"name": "should not be created"},
                )
                self.assertEqual(blocked.status_code, 403)

                allowed = client.post(
                    "/api/v1/projects",
                    headers={"X-CSRF-Token": fresh_token},
                    json={"name": "csrf-protected project"},
                )
                self.assertEqual(allowed.status_code, 200, allowed.text)
            finally:
                database.DB_PATH = old_db_path
                config.DATABASE_URL = old_database_url

    def test_approvals_endpoint_requires_authentication(self):
        client = TestClient(create_app())
        response = client.get("/approvals")
        self.assertEqual(response.status_code, 401)

    def test_api_routes_have_canonical_versioned_paths(self):
        client = TestClient(create_app())
        chat = client.get("/api/v1/chat/conversations")
        old_chat = client.get("/api/v1/api/chat/conversations")
        files = client.get("/api/v1/files")
        old_files = client.get("/api/v1/api/files")
        old_memory = client.get("/api/v1/api/memory")
        old_knowledge = client.get("/api/v1/api/knowledge/search?q=example")
        self.assertEqual(chat.status_code, 401)
        self.assertEqual(old_chat.status_code, 404)
        self.assertEqual(files.status_code, 401)
        self.assertEqual(old_files.status_code, 404)
        self.assertEqual(old_memory.status_code, 404)
        self.assertEqual(old_knowledge.status_code, 404)

    def test_state_changing_auth_route_requires_csrf_token(self):
        client = TestClient(create_app())
        response = client.post("/auth/logout")
        self.assertEqual(response.status_code, 403)

    def test_new_feature_apis_are_mounted_and_authenticated(self):
        client = TestClient(create_app())
        paths = [
            "/api/v1/projects",
            "/api/v1/artifacts",
            "/api/v1/missions",
            "/api/v1/workflows",
            "/api/v1/social-content",
            "/api/v1/social-campaigns",
            "/api/v1/connectors",
            "/api/v1/connectors/social-accounts",
            "/api/v1/research",
            "/api/v1/evidence",
            "/api/v1/memory",
            "/api/v1/knowledge/search?q=example",
        ]
        for path in paths:
            with self.subTest(path=path):
                response = client.get(path)
                self.assertEqual(response.status_code, 401)

    def test_registration_can_be_closed_by_operator(self):
        with patch.object(config, "REGISTRATION_OPEN", False):
            client = TestClient(create_app())
            token = client.get("/auth/csrf").json()["csrf_token"]
            response = client.post(
                "/auth/register",
                headers={"X-CSRF-Token": token},
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
