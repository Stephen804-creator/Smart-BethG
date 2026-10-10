from tests.base import SmartBethGTestCase
from services.auth_service import create_user
from repositories.conversation_repository import ConversationRepository
from services.training_export_service import TrainingExportService


class TestTrainingExportService(SmartBethGTestCase):
    def setUp(self):
        super().setUp()
        self.user = create_user("alice", "password123")
        self.repo = ConversationRepository()
        self.service = TrainingExportService()

    def test_real_ai_exchange_is_exported(self):
        cid = self.repo.create(self.user["id"])
        self.repo.add_message(cid, "user", "What's the capital of France?")
        self.repo.add_message(cid, "assistant", "Paris.", provider="anthropic", model="claude-sonnet-5")

        examples = self.service.export()
        self.assertEqual(len(examples), 1)
        self.assertEqual(
            examples[0]["messages"],
            [{"role": "user", "content": "What's the capital of France?"}, {"role": "assistant", "content": "Paris."}],
        )

    def test_honest_failure_message_is_excluded(self):
        """
        provider=None is exactly how ChatService marks the "isn't
        connected to an AI model yet" / "could not reach any provider"
        messages - these must never be used to teach a model to fail.
        """
        cid = self.repo.create(self.user["id"])
        self.repo.add_message(cid, "user", "hello")
        self.repo.add_message(cid, "assistant", "Smart BethG isn't connected to an AI model yet.")  # provider=None

        examples = self.service.export()
        self.assertEqual(examples, [])

    def test_synthesized_agent_exchange_is_excluded(self):
        """provider="agent" is how tool/memory/clarify synthesized replies are tagged - not real AI output."""
        cid = self.repo.create(self.user["id"])
        self.repo.add_message(cid, "user", "remember that I like Python")
        self.repo.add_message(cid, "assistant", 'Got it, I\'ll remember that: "I like Python"', provider="agent")

        examples = self.service.export()
        self.assertEqual(examples, [])

    def test_mixed_conversation_keeps_only_real_exchanges(self):
        cid = self.repo.create(self.user["id"])
        self.repo.add_message(cid, "user", "hello")
        self.repo.add_message(cid, "assistant", "not configured message")  # provider=None, excluded
        self.repo.add_message(cid, "user", "what is 2+2?")
        self.repo.add_message(cid, "assistant", "4", provider="openai", model="gpt-5.6-terra")

        examples = self.service.export()
        self.assertEqual(len(examples), 1)
        self.assertEqual(examples[0]["messages"], [
            {"role": "user", "content": "what is 2+2?"},
            {"role": "assistant", "content": "4"},
        ])

    def test_no_user_identity_in_export(self):
        cid = self.repo.create(self.user["id"])
        self.repo.add_message(cid, "user", "hi")
        self.repo.add_message(cid, "assistant", "hello!", provider="anthropic")

        examples = self.service.export()
        dumped = str(examples)
        self.assertNotIn(str(self.user["id"]), dumped)
        self.assertNotIn("alice", dumped)

    def test_unanswered_trailing_question_is_dropped_not_exported_incomplete(self):
        cid = self.repo.create(self.user["id"])
        self.repo.add_message(cid, "user", "answered question")
        self.repo.add_message(cid, "assistant", "a real answer", provider="google")
        self.repo.add_message(cid, "user", "unanswered question")  # no qualifying reply follows

        examples = self.service.export()
        self.assertEqual(len(examples), 1)
        contents = [m["content"] for m in examples[0]["messages"]]
        self.assertNotIn("unanswered question", contents)

    def test_count_exportable_matches_export_length(self):
        cid = self.repo.create(self.user["id"])
        self.repo.add_message(cid, "user", "hi")
        self.repo.add_message(cid, "assistant", "hello", provider="anthropic")
        self.assertEqual(self.service.count_exportable(), len(self.service.export()))

    def test_empty_database_exports_nothing(self):
        self.assertEqual(self.service.export(), [])
        self.assertEqual(self.service.count_exportable(), 0)
