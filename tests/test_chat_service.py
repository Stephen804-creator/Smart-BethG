from tests.base import SmartBethGTestCase
from services.auth_service import create_user
from services.chat_service import ChatService


class TestChatServiceNoProviderConfigured(SmartBethGTestCase):
    """
    These run with no API keys set (the default test environment), which
    is itself an important case: chat must degrade honestly, never
    fabricate a reply.
    """

    def setUp(self):
        super().setUp()
        self.user = create_user("alice", "password123")
        self.service = ChatService()

    def test_send_without_provider_is_honest_not_fake(self):
        result = self.service.send(self.user["id"], "hello")
        self.assertFalse(result["provider_configured"])
        self.assertIn("isn't connected", result["reply"])

    def test_send_persists_user_and_assistant_messages(self):
        result = self.service.send(self.user["id"], "hello")
        history = self.service.history(self.user["id"], result["conversation_id"])
        roles = [m["role"] for m in history]
        self.assertEqual(roles, ["user", "assistant"])

    def test_empty_message_rejected(self):
        with self.assertRaises(ValueError):
            self.service.send(self.user["id"], "   ")

    def test_conversation_is_auto_titled_from_first_message(self):
        result = self.service.send(self.user["id"], "What is the capital of France?")
        conversations = self.service.list_conversations(self.user["id"])
        self.assertEqual(len(conversations), 1)
        self.assertTrue(conversations[0]["title"].startswith("What is the capital"))

    def test_second_message_reuses_conversation_and_title(self):
        first = self.service.send(self.user["id"], "First message here")
        self.service.send(self.user["id"], "Second message", conversation_id=first["conversation_id"])
        conversations = self.service.list_conversations(self.user["id"])
        self.assertEqual(len(conversations), 1)
        self.assertTrue(conversations[0]["title"].startswith("First message"))

    def test_history_for_unowned_conversation_is_empty(self):
        other = create_user("bob", "password123")
        result = self.service.send(self.user["id"], "hello")
        history = self.service.history(other["id"], result["conversation_id"])
        self.assertEqual(history, [])

    def test_usage_totals_zero_when_nothing_sent(self):
        totals = self.service.usage(self.user["id"])
        self.assertEqual(totals["totals"]["input_tokens"], 0)
        self.assertEqual(totals["totals"]["message_count"], 0)
