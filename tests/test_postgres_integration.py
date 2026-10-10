"""Smoke tests for the production PostgreSQL adapter (run by CI's PG service)."""
import uuid
import unittest
from concurrent.futures import ThreadPoolExecutor

from database import initialize_database
from repositories.conversation_repository import ConversationRepository
from services.approval_service import ApprovalService
from services.auth_service import create_user
from services.rate_limiter import check_rate_limit
from services.usage_budget_service import UsageBudgetService


class TestPostgreSQLIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        initialize_database()

    def test_user_conversation_and_approval_round_trip(self):
        suffix = uuid.uuid4().hex[:12]
        user = create_user("pg-" + suffix, "test-password-123")
        self.assertIsNotNone(user)
        self.assertGreater(user["id"], 0)

        repo = ConversationRepository()
        conversation_id = repo.create(user["id"], "PostgreSQL integration")
        self.assertGreater(conversation_id, 0)
        repo.add_message(conversation_id, "user", "hello")
        messages = repo.list_messages(conversation_id)
        self.assertEqual(messages[0]["content"], "hello")

        approvals = ApprovalService()
        pending = approvals.create(user["id"], "git.write", "workspace:default")
        decided = approvals.decide(pending["id"], user["id"], True)
        self.assertEqual(decided["status"], "approved")

    def test_database_backed_usage_budget_reservation(self):
        suffix = uuid.uuid4().hex[:12]
        user = create_user("pg-budget-" + suffix, "test-password-123")
        budget = UsageBudgetService()
        reservation = budget.reserve(user["id"], "openrouter", "openrouter/free", 100, 100)
        self.assertTrue(budget.reconcile(reservation["id"], 90, 80))
        usage = budget.get_usage(user["id"])
        self.assertEqual(usage["actual_tokens"], 170)
        self.assertEqual(usage["requests"], 1)

    def test_database_backed_rate_limiter(self):
        key = "pg-integration:" + uuid.uuid4().hex
        self.assertTrue(check_rate_limit(key))


    def test_database_rate_limiter_is_atomic_under_concurrency(self):
        key = "pg-concurrency:" + uuid.uuid4().hex
        with ThreadPoolExecutor(max_workers=12) as pool:
            results = list(pool.map(
                lambda _: check_rate_limit(key, max_attempts=5, window_seconds=60),
                range(24),
            ))
        self.assertEqual(sum(results), 5)


if __name__ == "__main__":
    unittest.main()
