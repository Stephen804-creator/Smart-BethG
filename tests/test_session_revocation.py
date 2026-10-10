import unittest
from unittest.mock import patch

from fastapi import HTTPException
from starlette.requests import Request

from api.dependencies import get_current_user
from services.auth_service import create_user, get_user_by_id, revoke_user_sessions
from tests.base import SmartBethGTestCase


class TestSessionRevocation(SmartBethGTestCase):
    def test_logout_revocation_invalidates_previously_issued_session(self):
        created = create_user("session-owner", "password123")
        original = get_user_by_id(created["id"])
        self.assertEqual(original["session_version"], 0)

        self.assertTrue(revoke_user_sessions(created["id"]))
        current = get_user_by_id(created["id"])
        self.assertEqual(current["session_version"], 1)

        scope = {
            "type": "http",
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": "/api/v1/projects",
            "raw_path": b"/api/v1/projects",
            "query_string": b"",
            "headers": [],
            "server": ("testserver", 80),
            "client": ("127.0.0.1", 12345),
            "session": {
                "user_id": created["id"],
                "session_version": original["session_version"],
            },
        }
        request = Request(scope)
        with patch("api.dependencies.get_user_by_id", return_value=current):
            with self.assertRaises(HTTPException) as caught:
                get_current_user(request)
        self.assertEqual(caught.exception.status_code, 401)
        self.assertEqual(request.session, {})

    def test_current_session_version_remains_valid(self):
        created = create_user("session-owner-valid", "password123")
        current = get_user_by_id(created["id"])
        scope = {
            "type": "http",
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": "/api/v1/projects",
            "raw_path": b"/api/v1/projects",
            "query_string": b"",
            "headers": [],
            "server": ("testserver", 80),
            "client": ("127.0.0.1", 12345),
            "session": {
                "user_id": created["id"],
                "session_version": current["session_version"],
            },
        }
        request = Request(scope)
        with patch("api.dependencies.get_user_by_id", return_value=current):
            result = get_current_user(request)
        self.assertEqual(result["id"], created["id"])

    def test_revoking_unknown_user_returns_false(self):
        self.assertFalse(revoke_user_sessions(999999))


if __name__ == "__main__":
    unittest.main()
