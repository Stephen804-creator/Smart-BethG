import os
from unittest.mock import patch

from tests.base import SmartBethGTestCase
from services.auth_service import create_user
from services.usage_budget_service import UsageBudgetService, BudgetExceededError


class TestUsageBudgetService(SmartBethGTestCase):
    def setUp(self):
        super().setUp()
        self.user = create_user("budget-user", "password123")
        self.other = create_user("budget-other", "password123")
        self.service = UsageBudgetService()

    def test_reserve_and_reconcile_usage(self):
        reservation = self.service.reserve(self.user["id"], "openai", "gpt-6-luna", 100, 200)
        self.assertTrue(self.service.reconcile(reservation["id"], 90, 150))
        usage = self.service.get_usage(self.user["id"])
        self.assertEqual(usage["actual_tokens"], 240)
        self.assertEqual(usage["requests"], 1)
        self.assertGreaterEqual(usage["estimated_spend_usd"], 0)

    def test_per_user_budget_is_enforced(self):
        with patch("services.usage_budget_service.config.USER_DAILY_TOKEN_BUDGET", 250):
            with patch("services.usage_budget_service.config.GLOBAL_DAILY_TOKEN_BUDGET", 10000):
                self.service.reserve(self.user["id"], "openai", "gpt-6-luna", 50, 100)
                with self.assertRaises(BudgetExceededError):
                    self.service.reserve(self.user["id"], "openai", "gpt-6-luna", 50, 100)
                # A different user has a separate user budget, subject to the global ceiling.
                self.service.reserve(self.other["id"], "openai", "gpt-6-luna", 50, 100)

    def test_global_budget_is_shared_across_users(self):
        with patch("services.usage_budget_service.config.USER_DAILY_TOKEN_BUDGET", 10000):
            with patch("services.usage_budget_service.config.GLOBAL_DAILY_TOKEN_BUDGET", 350):
                self.service.reserve(self.user["id"], "openai", "gpt-6-luna", 50, 100)
                with self.assertRaises(BudgetExceededError):
                    self.service.reserve(self.other["id"], "openai", "gpt-6-luna", 50, 100)

    def test_unknown_model_uses_conservative_pricing(self):
        pricing = self.service._pricing("openai", "unlisted-model")
        self.assertEqual(pricing["input"], 20.0)
        self.assertEqual(pricing["output"], 100.0)


if __name__ == "__main__":
    import unittest
    unittest.main()
