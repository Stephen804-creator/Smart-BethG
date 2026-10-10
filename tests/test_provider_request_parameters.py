import unittest
from types import SimpleNamespace

from providers.openai_provider import OpenAIProvider
from providers.groq_provider import GroqProvider
from providers.openrouter_provider import OpenRouterProvider


class FakeCompletions:
    def __init__(self):
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))],
            usage=SimpleNamespace(prompt_tokens=5, completion_tokens=7),
        )


class TestProviderRequestParameters(unittest.TestCase):
    def make_provider(self, cls):
        provider = cls.__new__(cls)
        provider._client = SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions()))
        provider.model = "test-model"
        return provider

    def test_openai_uses_completion_token_parameter(self):
        provider = self.make_provider(OpenAIProvider)
        result = provider.generate([{"role": "user", "content": "hi"}], max_tokens=123)
        self.assertEqual(provider._client.chat.completions.kwargs["max_completion_tokens"], 123)
        self.assertNotIn("max_tokens", provider._client.chat.completions.kwargs)
        self.assertEqual(result["output_tokens"], 7)

    def test_openai_compatible_hosts_keep_max_tokens_parameter(self):
        for cls in (GroqProvider, OpenRouterProvider):
            with self.subTest(provider=cls.__name__):
                provider = self.make_provider(cls)
                provider.generate([{"role": "user", "content": "hi"}], max_tokens=321)
                self.assertEqual(provider._client.chat.completions.kwargs["max_tokens"], 321)
                self.assertNotIn("max_completion_tokens", provider._client.chat.completions.kwargs)


if __name__ == "__main__":
    unittest.main()
