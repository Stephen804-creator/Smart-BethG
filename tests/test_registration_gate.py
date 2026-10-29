import unittest
from unittest.mock import patch

from fastapi import HTTPException
from starlette.requests import Request

import config
from routes.auth import RegisterRequest, register


def _request():
    return Request({
        "type": "http",
        "method": "POST",
        "path": "/auth/register",
        "headers": [],
        "query_string": b"",
        "server": ("testserver", 80),
        "client": ("127.0.0.1", 12345),
        "scheme": "http",
    })


class TestRegistrationGate(unittest.TestCase):
    def test_closed_registration_rejects_before_rate_limiter_or_database(self):
        previous = config.REGISTRATION_OPEN
        config.REGISTRATION_OPEN = False
        try:
            with patch("routes.auth.check_rate_limit", side_effect=AssertionError(
                "rate limiter must not run when registration is disabled"
            )), patch("routes.auth.create_user", side_effect=AssertionError(
                "database account creation must not run when registration is disabled"
            )):
                with self.assertRaises(HTTPException) as raised:
                    register(RegisterRequest(username="new-user", password="safe-test-password"), _request())
            self.assertEqual(raised.exception.status_code, 403)
            self.assertEqual(raised.exception.detail, "Registration is currently disabled.")
        finally:
            config.REGISTRATION_OPEN = previous


if __name__ == "__main__":
    unittest.main()
