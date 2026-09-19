from .provider_base import ProviderBase


class OpenAIProvider(ProviderBase):
    """Real OpenAI Chat Completions provider.

    Requires the `openai` package (already in requirements.txt) and an
    API key. If no key is configured, generate() raises RuntimeError
    rather than returning a fabricated response.
    """

    name = "openai"

    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        self.api_key = api_key
        self.model = model
        self._client = None
        if api_key:
            from openai import OpenAI
            self._client = OpenAI(api_key=api_key)

    def generate(self, messages, model=None, **kwargs):
        if not self._client:
            raise RuntimeError(
                "OpenAI provider has no API key configured (set OPENAI_API_KEY)."
            )
        response = self._client.chat.completions.create(
            model=model or self.model,
            messages=messages,
            max_tokens=kwargs.get("max_tokens", 1024),
        )
        return (response.choices[0].message.content or "").strip()
