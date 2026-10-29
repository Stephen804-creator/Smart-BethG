"""Regression tests for HTTP security boundaries and tenant isolation.

These tests deliberately use SmartBethGTestCase so every database-backed test
runs against an isolated PostgreSQL schema. Do not replace this with SQLite or
mutate database configuration in a test: doing so would test a different
persistence path from the application's supported runtime.
"""

import os
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from fastapi import HTTPException

from tests.base import SmartBethGTestCase

import config
from main_fastapi import create_app
from services.approval_service import ApprovalService
from services.tool_service import resolve_workspace_root


class TestHttpSecurityBoundaries(SmartBethGTestCase):
    """Protect externally observable HTTP security and routing contracts.

    The assertions here are regression guards: refactoring app construction or
    middleware must not silently weaken headers, CSRF enforcement, authentication,
    CORS restrictions, registration policy, or canonical API paths.
    """
    def test_security_headers_are_present(self):
        # These headers reduce MIME sniffing, clickjacking, referrer leakage, and
        # unsafe script/object embedding. CSP is report-only during rollout, so
        # this test intentionally verifies the report-only header rather than
        # asserting that an enforcing Content-Security-Policy is already active.
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
        # A valid login establishes the session first; the next requests prove
        # that cookie-authenticated writes are rejected without a CSRF token and
        # accepted with the token issued for that authenticated session.
        from services.auth_service import create_user

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

    def test_approvals_endpoint_requires_authentication(self):
        client = TestClient(create_app())
        response = client.get("/approvals")
        self.assertEqual(response.status_code, 401)

    def test_api_routes_have_canonical_versioned_paths(self):
        # Canonical /api/v1 paths must remain mounted. Old duplicated /api/v1/api
        # aliases should stay absent so clients do not depend on accidental routes.
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
        # A 401 response proves the route exists and its authentication boundary
        # runs before protected data can be read; a 404 would indicate a missing
        # route, while a 200 would indicate a possible authorization regression.
        client = TestClient(create_app())
        paths = [
            "/api/v1/projects",
            "/api/v1/artifacts",
            "/api/v1/missions",
            "/api/v1/workflows",
            "/api/v1/social-content",
            "/api/v1/research",
            "/api/v1/evidence",
            "/api/v1/memory",
            "/api/v1/knowledge/search?q=example",
        ]
        for path in paths:
            with self.subTest(path=path):
                response = client.get(path)
                self.assertEqual(response.status_code, 401)

    def test_registration_is_public_and_does_not_require_an_invite_code(self):
        client = TestClient(create_app())
        token = client.get("/auth/csrf").json()["csrf_token"]
        with patch("routes.auth.create_user", return_value={
            "id": 987654, "username": "public-signup-test", "role": "user"
        }):
            response = client.post(
                "/auth/register",
                headers={"X-CSRF-Token": token},
                json={"username": "public-signup-test", "password": "safe-test-password"},
            )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(response.json().get("created"))
        self.assertEqual(response.json()["user"]["role"], "user")

    def test_ordinary_user_cannot_access_admin_only_endpoints(self):
        from services.auth_service import create_user

        username = "ordinary-admin-boundary-test"
        create_user(username, "admin-boundary-test-password")
        client = TestClient(create_app())
        token = client.get("/auth/csrf").json()["csrf_token"]
        login = client.post(
            "/auth/login",
            headers={"X-CSRF-Token": token},
            json={"username": username, "password": "admin-boundary-test-password"},
        )
        self.assertEqual(login.status_code, 200, login.text)

        audit = client.get("/audit/all")
        training_export = client.get("/admin/training-export/preview")
        self.assertEqual(audit.status_code, 403, audit.text)
        self.assertEqual(training_export.status_code, 403, training_export.text)

    def test_cors_preflight_accepts_only_configured_origin(self):
        # Browsers should receive CORS permission only for explicitly configured
        # origins; a successful preflight for an arbitrary origin could expose
        # credentialed endpoints to an untrusted site.
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


class TestApprovalService(SmartBethGTestCase):
    """Verify approval state is durable and restricted to its owning user.

    These are database-backed service tests, not isolated mocks: approval
    ownership, persistence, and one-way decisions must hold at the service layer
    even when callers bypass the HTTP routes.
    """
    def setUp(self):
        super().setUp()
        self.service = ApprovalService()

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
    """Check filesystem tenant boundaries without needing a database.

    A temporary directory prevents the test from touching real user files while
    allowing the path resolver's isolation rules to be checked directly.
    """
    def test_workspaces_are_isolated_by_authenticated_user(self):
        with tempfile.TemporaryDirectory() as root:
            with patch.dict(config.STORAGE_DIRS, {"projects": root}):
                user_one = resolve_workspace_root(101, "default")
                user_two = resolve_workspace_root(202, "default")
                self.assertNotEqual(user_one, user_two)
                self.assertTrue(user_one.startswith(os.path.join(root, "101")))
                self.assertTrue(user_two.startswith(os.path.join(root, "202")))

    def test_workspace_name_cannot_escape_user_root(self):
        # Treat the workspace name as untrusted input. Traversal strings such as
        # ../../another-user must never resolve outside the authenticated user's
        # storage directory, even if the caller supplies a malicious name.
        with tempfile.TemporaryDirectory() as root:
            with patch.dict(config.STORAGE_DIRS, {"projects": root}):
                resolved = resolve_workspace_root(101, "../../another-user")
                self.assertTrue(resolved.startswith(os.path.join(root, "101")))
                self.assertNotIn("..", os.path.relpath(resolved, os.path.join(root, "101")))


if __name__ == "__main__":
    unittest.main()
