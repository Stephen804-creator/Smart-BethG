import unittest

from fastapi import HTTPException

from api.dependencies import require_role


class TestRequireRole(unittest.TestCase):
    """
    The actual security boundary protecting admin-only routes (the
    training exporter, GET /audit/all). Tested by calling the inner
    check function directly with a user dict, bypassing FastAPI's
    request-handling machinery (not installed in this environment) -
    the authorization decision itself doesn't depend on that machinery.
    """

    def test_admin_user_passes(self):
        check = require_role("admin")
        result = check(user={"id": 1, "role": "admin"})
        self.assertEqual(result["role"], "admin")

    def test_non_admin_user_rejected(self):
        check = require_role("admin")
        with self.assertRaises(HTTPException) as ctx:
            check(user={"id": 2, "role": "user"})
        self.assertEqual(ctx.exception.status_code, 403)

    def test_missing_role_fails_closed(self):
        """A user dict with no role at all must never be treated as authorized."""
        check = require_role("admin")
        with self.assertRaises(HTTPException):
            check(user={"id": 3})

    def test_unknown_role_string_fails_closed(self):
        check = require_role("admin")
        with self.assertRaises(HTTPException):
            check(user={"id": 4, "role": "superadmin"})
