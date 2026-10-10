from tests.base import SmartBethGTestCase
from services.auth_service import create_user
from services.chat_service import ChatService
from providers.provider_manager import provider_manager
import config


class _FailingProvider:
    def generate(self, messages, model=None, **kwargs):
        raise RuntimeError("simulated outage")


class _WorkingProvider:
    def generate(self, messages, model=None, **kwargs):
        return {"text": "fallback reply", "input_tokens": 3, "output_tokens": 5}


class TestChatServiceProviderFallback(SmartBethGTestCase):
    def setUp(self):
        super().setUp()
        self.user = create_user("alice", "password123")
        self.service = ChatService()

        # Save real state and substitute controllable fake providers on
        # the shared provider_manager singleton chat_service.py imports.
        self._orig_platform = dict(provider_manager.platform)
        self._orig_default = config.DEFAULT_PROVIDER
        config.DEFAULT_PROVIDER = ""

    def tearDown(self):
        provider_manager.platform = self._orig_platform
        config.DEFAULT_PROVIDER = self._orig_default
        super().tearDown()

    def test_falls_back_to_working_provider_after_failure(self):
        provider_manager.platform = {"anthropic": _FailingProvider(), "openai": _WorkingProvider()}
        result = self.service.send(self.user["id"], "hello")
        self.assertEqual(result["reply"], "fallback reply")
        self.assertEqual(result["provider"], "openai")
        self.assertTrue(result["fallback_used"])

    def test_stored_message_records_the_provider_that_actually_answered(self):
        provider_manager.platform = {"anthropic": _FailingProvider(), "openai": _WorkingProvider()}
        result = self.service.send(self.user["id"], "hello")
        history = self.service.history(self.user["id"], result["conversation_id"])
        assistant_msg = [m for m in history if m["role"] == "assistant"][0]
        self.assertEqual(assistant_msg["provider"], "openai")

    def test_no_fallback_needed_when_first_provider_works(self):
        provider_manager.platform = {"anthropic": _WorkingProvider(), "openai": _WorkingProvider()}
        result = self.service.send(self.user["id"], "hello")
        self.assertEqual(result["provider"], "anthropic")
        self.assertFalse(result["fallback_used"])

    def test_honest_failure_when_every_provider_fails(self):
        provider_manager.platform = {"anthropic": _FailingProvider(), "openai": _FailingProvider()}
        result = self.service.send(self.user["id"], "hello")
        self.assertTrue(result.get("error"))
        self.assertIn("anthropic", result["reply"])
        self.assertIn("openai", result["reply"])

    def test_every_attempt_is_recorded_for_evaluation(self):
        """
        The failed attempt must be visible too, not just the eventual
        successful one - otherwise a flaky provider hiding behind
        fallback would look perfectly healthy.
        """
        provider_manager.platform = {"anthropic": _FailingProvider(), "openai": _WorkingProvider()}
        self.service.send(self.user["id"], "hello")
        stats = self.service.eval_service.stats()
        by_provider = {row["provider"]: row for row in stats}
        self.assertEqual(by_provider["anthropic"]["successes"], 0)
        self.assertEqual(by_provider["anthropic"]["attempts"], 1)
        self.assertEqual(by_provider["openai"]["successes"], 1)
