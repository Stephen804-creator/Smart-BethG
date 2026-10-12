from unittest.mock import patch

from services.chat_service import ChatService
from services.sniper_memory import SniperMemory
from tests.base import SmartBethGTestCase


class FakeConversationRepository:
    def __init__(self, messages):
        self.messages = list(messages)
        self.next_id = 1000

    def get(self, conversation_id, user_id):
        return None

    def create(self, user_id):
        return 77

    def add_message(self, conversation_id, role, content, **kwargs):
        self.next_id += 1
        self.messages.append({
            "id": self.next_id, "role": role, "content": content,
            "provider": kwargs.get("provider"), "model": kwargs.get("model"),
            "created_at": "2026-10-12T00:00:00",
        })
        return self.next_id

    def set_title(self, conversation_id, title):
        pass

    def list_messages_for_context(self, conversation_id, limit=2000):
        return self.messages[-limit:]

    def touch(self, conversation_id):
        pass


class FakeMemoryService:
    def recall_context(self, *args, **kwargs):
        return ""


class FakeKnowledgeService:
    def has_knowledge(self, user_id):
        return False


class FakeBudgetService:
    def estimate_input_tokens(self, messages):
        return sum(len(item["content"]) for item in messages) // 4

    def reserve(self, *args, **kwargs):
        return {"id": "reservation-1"}

    def reconcile(self, *args, **kwargs):
        pass

    def mark_failed(self, *args, **kwargs):
        pass


class FakeEvaluationService:
    def record_call(self, *args, **kwargs):
        pass


class FakeProvider:
    def __init__(self):
        self.messages = None

    def generate(self, messages, **kwargs):
        self.messages = messages
        return {"text": "I retained the relevant context.", "input_tokens": 100, "output_tokens": 10}


class TestSniperMemoryChatIntegration(SmartBethGTestCase):
    def test_chat_sends_selected_history_not_the_full_transcript(self):
        history = []
        for index in range(45):
            history.extend([
                {"id": index * 2 + 1, "role": "user", "content": f"Unrelated subject {index}: " + ("generic words " * 15)},
                {"id": index * 2 + 2, "role": "assistant", "content": f"Response subject {index}: " + ("generic answer " * 15)},
            ])
        history[0]["content"] = "We decided production database is PostgreSQL."
        history[1]["content"] = "PostgreSQL is the selected production database."
        current_message = "Which database did we choose for production?"

        repo = FakeConversationRepository(history)
        provider = FakeProvider()
        service = ChatService(
            repo=repo,
            eval_service=FakeEvaluationService(),
            memory_service=FakeMemoryService(),
            knowledge_service=FakeKnowledgeService(),
            budget_service=FakeBudgetService(),
            sniper_memory=SniperMemory(recent_turns=2, relevant_turns=2, max_context_chars=3000),
        )

        with patch("services.chat_service.provider_manager.choose_auto", return_value=("fake", "fake-model")), \
             patch("services.chat_service.provider_manager.get", return_value=provider), \
             patch("services.chat_service.provider_manager.fallback_candidates", return_value=[]):
            result = service.send(1, current_message)

        sent_text = "\n".join(message["content"] for message in provider.messages)
        self.assertIn("PostgreSQL", sent_text)
        self.assertIn(current_message, sent_text)
        self.assertLess(len(provider.messages), len(history) + 1)
        self.assertGreater(result["sniper_memory"]["saved_chars"], 0)
        self.assertEqual(result["reply"], "I retained the relevant context.")
