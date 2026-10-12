import unittest
from types import SimpleNamespace
from unittest.mock import patch

import config
from providers.anthropic_provider import AnthropicProvider
from providers.openai_provider import OpenAIProvider
from services.prompt_cache import make_prompt_cache_key


class FakeAnthropicMessages:
    def __init__(self):
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text="cached response")],
            usage=SimpleNamespace(
                input_tokens=120,
                output_tokens=9,
                cache_read_input_tokens=80,
                cache_creation_input_tokens=0,
            ),
        )


class FakeOpenAICompletions:
    def __init__(self):
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="cached response"))],
            usage=SimpleNamespace(
                prompt_tokens=120,
                completion_tokens=9,
                prompt_tokens_details=SimpleNamespace(cached_tokens=80),
            ),
        )


class TestPromptCacheKey(unittest.TestCase):
    def setUp(self):
        self._enabled = config.PROMPT_CACHING_ENABLED
        self._secret = config.SECRET_KEY
        config.PROMPT_CACHING_ENABLED = True
        config.SECRET_KEY = "unit-test-secret"

    def tearDown(self):
        config.PROMPT_CACHING_ENABLED = self._enabled
        config.SECRET_KEY = self._secret

    def test_key_is_stable_opaque_and_scoped(self):
        prefix = [{"role": "user", "content": "stable project context"}]
        first = make_prompt_cache_key(10, "model-a", prefix, 99)
        self.assertEqual(first, make_prompt_cache_key(10, "model-a", prefix, 99))
        self.assertEqual(len(first), 64)
        self.assertNotEqual(first, make_prompt_cache_key(11, "model-a", prefix, 99))
        self.assertNotEqual(first, make_prompt_cache_key(10, "model-b", prefix, 99))
        self.assertNotEqual(first, make_prompt_cache_key(10, "model-a", prefix, 100))
        self.assertNotEqual(first, make_prompt_cache_key(10, "model-a", [{"role": "user", "content": "changed"}], 99))

    def test_disabled_cache_returns_no_key(self):
        config.PROMPT_CACHING_ENABLED = False
        self.assertIsNone(make_prompt_cache_key(10, "model-a", [], 99))


class TestAnthropicPromptCaching(unittest.TestCase):
    def setUp(self):
        self._enabled = config.PROMPT_CACHING_ENABLED
        self._min_chars = config.PROMPT_CACHE_ANTHROPIC_MIN_PREFIX_CHARS
        config.PROMPT_CACHING_ENABLED = True
        config.PROMPT_CACHE_ANTHROPIC_MIN_PREFIX_CHARS = 10

    def tearDown(self):
        config.PROMPT_CACHING_ENABLED = self._enabled
        config.PROMPT_CACHE_ANTHROPIC_MIN_PREFIX_CHARS = self._min_chars

    def make_provider(self):
        provider = AnthropicProvider.__new__(AnthropicProvider)
        fake_messages = FakeAnthropicMessages()
        provider._client = SimpleNamespace(messages=fake_messages)
        provider.model = "test-model"
        return provider, fake_messages

    def test_adds_ephemeral_breakpoint_to_end_of_large_prefix(self):
        provider, fake = self.make_provider()
        messages = [
            {"role": "user", "content": "stable prefix long enough"},
            {"role": "user", "content": "current question"},
        ]
        result = provider.generate(messages, cache_prefix_message_count=1, max_tokens=40)
        first_content = fake.kwargs["messages"][0]["content"]
        self.assertEqual(first_content[0]["cache_control"], {"type": "ephemeral"})
        self.assertEqual(fake.kwargs["messages"][1]["content"], "current question")
        self.assertEqual(messages[0]["content"], "stable prefix long enough")
        self.assertEqual(result["cached_input_tokens"], 80)
        self.assertIsNone(result["cache_creation_input_tokens"])

    def test_does_not_add_breakpoint_to_small_prefix(self):
        config.PROMPT_CACHE_ANTHROPIC_MIN_PREFIX_CHARS = 1000
        provider, fake = self.make_provider()
        provider.generate(
            [{"role": "user", "content": "short"}, {"role": "user", "content": "question"}],
            cache_prefix_message_count=1,
        )
        self.assertEqual(fake.kwargs["messages"][0]["content"], "short")


class TestOpenAIPromptCaching(unittest.TestCase):
    def setUp(self):
        self._enabled = config.PROMPT_CACHING_ENABLED
        config.PROMPT_CACHING_ENABLED = True

    def tearDown(self):
        config.PROMPT_CACHING_ENABLED = self._enabled

    def make_provider(self, cls=OpenAIProvider):
        provider = cls.__new__(cls)
        fake_completions = FakeOpenAICompletions()
        provider._client = SimpleNamespace(chat=SimpleNamespace(completions=fake_completions))
        provider.model = "test-model"
        return provider, fake_completions

    def test_openai_passes_cache_key_and_reports_cached_tokens(self):
        provider, fake = self.make_provider()
        result = provider.generate(
            [{"role": "user", "content": "hello"}],
            max_tokens=100,
            prompt_cache_key="a" * 64,
        )
        self.assertEqual(fake.kwargs["prompt_cache_key"], "a" * 64)
        self.assertEqual(result["cached_input_tokens"], 80)
        self.assertEqual(result["cache_creation_input_tokens"], 0)

    def test_cache_key_is_not_sent_to_openai_compatible_hosts(self):
        from providers.groq_provider import GroqProvider
        from providers.openrouter_provider import OpenRouterProvider

        for cls in (GroqProvider, OpenRouterProvider):
            with self.subTest(provider=cls.__name__):
                provider, fake = self.make_provider(cls)
                provider.generate(
                    [{"role": "user", "content": "hello"}],
                    max_tokens=100,
                    prompt_cache_key="a" * 64,
                )
                self.assertNotIn("prompt_cache_key", fake.kwargs)

    def test_disabled_cache_does_not_send_openai_cache_key(self):
        config.PROMPT_CACHING_ENABLED = False
        provider, fake = self.make_provider()
        provider.generate(
            [{"role": "user", "content": "hello"}],
            max_tokens=100,
            prompt_cache_key="a" * 64,
        )
        self.assertNotIn("prompt_cache_key", fake.kwargs)


from services.auth_service import create_user
from services.chat_service import ChatService
from tests.base import SmartBethGTestCase
from unittest.mock import patch


class FakeMemoryService:
    def recall_context(self, user_id, workspace, conversation_id):
        return "Stable project context " * 100


class FakeKnowledgeService:
    def has_knowledge(self, user_id):
        return False

    def recall_context(self, user_id, message):
        return None


class FakeChatProvider:
    name = "openai"

    def __init__(self):
        self.kwargs = None

    def generate(self, messages, model=None, **kwargs):
        self.kwargs = kwargs
        return {
            "text": "hello from provider",
            "input_tokens": 25,
            "output_tokens": 5,
            "cached_input_tokens": 10,
            "cache_creation_input_tokens": None,
        }


class TestChatServicePromptCaching(SmartBethGTestCase):
    def test_chat_supplies_scoped_cache_key_and_returns_cache_metrics(self):
        user = create_user("cache-user", "password123")
        provider = FakeChatProvider()
        service = ChatService(
            memory_service=FakeMemoryService(),
            knowledge_service=FakeKnowledgeService(),
        )
        with patch("services.chat_service.provider_manager.choose_auto", return_value=("openai", "test-model")), \
             patch("services.chat_service.provider_manager.get", return_value=provider), \
             patch("services.chat_service.provider_manager.fallback_candidates", return_value=[]):
            result = service.send(user["id"], "continue the project")

        self.assertEqual(len(provider.kwargs["prompt_cache_key"]), 64)
        self.assertEqual(result["prompt_cache"]["cached_input_tokens"], 10)
        self.assertIsNone(result["prompt_cache"]["cache_creation_input_tokens"])


if __name__ == "__main__":
    unittest.main()
