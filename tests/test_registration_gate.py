import unittest
from unittest.mock import patch

from starlette.requests import Request

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


class TestPublicRegistration(unittest.TestCase):
    def test_registration_creates_an_ordinary_user_without_invite_code(self):
        created_user = {"id": 123, "username": "public-user", "role": "user"}
        with patch("routes.auth.check_rate_limit", return_value=True), patch(
            "routes.auth.create_user", return_value=created_user
        ) as create:
            response = register(
                RegisterRequest(username="public-user", password="safe-test-password"),
                _request(),
            )
        self.assertTrue(response["created"])
        self.assertEqual(response["user"]["role"], "user")
        create.assert_called_once_with("public-user", "safe-test-password")


if __name__ == "__main__":
    unittest.main()
