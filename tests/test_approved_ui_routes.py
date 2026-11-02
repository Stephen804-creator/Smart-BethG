"""Smoke tests for the approved first-run and chat-first UI routes."""
from fastapi.testclient import TestClient

from main_fastapi import create_app
from tests.base import SmartBethGTestCase


class TestApprovedUiRoutes(SmartBethGTestCase):
    def setUp(self):
        super().setUp()
        self.client = TestClient(create_app())

    def test_onboarding_screen_is_public_and_has_four_steps(self):
        response = self.client.get("/onboarding")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Meet Smart BethG", response.text)
        self.assertIn("Do real work", response.text)
        self.assertIn("Connect your tools", response.text)
        self.assertIn("You choose how it works", response.text)
        self.assertIn("onboarding.css", response.text)

    def test_home_requires_authentication(self):
        response = self.client.get("/", follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["location"], "/login")


if __name__ == "__main__":
    import unittest
    unittest.main()
