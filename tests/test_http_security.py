import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

import config
from main_fastapi import create_app


class TestHttpSecurityBoundaries(unittest.TestCase):
    def test_approvals_endpoint_requires_authentication(self):
        client = TestClient(create_app())
        response = client.get("/approvals")
        self.assertEqual(response.status_code, 401)

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


if __name__ == "__main__":
    unittest.main()
