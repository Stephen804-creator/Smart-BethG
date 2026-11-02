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
        self.assertIn("onboarding.css", response.text)
        self.assertIn("onboarding.js", response.text)
        script = self.client.get("/static/js/onboarding.js")
        self.assertEqual(script.status_code, 200)
        self.assertIn("Do real work", script.text)
        self.assertIn("Connect your tools", script.text)
        self.assertIn("You choose how it works", script.text)

    def test_public_website_uses_approved_marketing_structure(self):
        response = self.client.get("/welcome")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Learn</span> as you", response.text)
        self.assertIn("No invite needed. Free to start.", response.text)
        self.assertIn("marketing.css", response.text)

    def test_public_pricing_page_matches_approved_plan_structure(self):
        response = self.client.get("/pricing")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Simple pricing", response.text)
        self.assertIn("Pay as you go", response.text)
        self.assertIn("₦2,500", response.text)
        self.assertIn("pricing.css", response.text)

    def test_home_requires_authentication(self):
        response = self.client.get("/", follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["location"], "/welcome")


if __name__ == "__main__":
    import unittest
    unittest.main()
