"""Smoke tests for the production PostgreSQL adapter (run by CI's PG service)."""
import uuid
import unittest

from database import initialize_database
from repositories.conversation_repository import ConversationRepository
from services.approval_service import ApprovalService
from services.auth_service import create_user
from services.rate_limiter import check_rate_limit


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

    def test_database_backed_rate_limiter(self):
        key = "pg-integration:" + uuid.uuid4().hex
        self.assertTrue(check_rate_limit(key))


if __name__ == "__main__":
    unittest.main()
