from .provider_base import ProviderBase
from .model_catalog import model_for_tier


class AnthropicProvider(ProviderBase):
    """Real Anthropic Messages API provider.

    Requires the `anthropic` package (already in requirements.txt) and an
    API key. If no key is configured, generate() raises RuntimeError with
    an honest message rather than returning a fabricated response.
    """

    name = "anthropic"

    def __init__(self, api_key: str, model: str = None):
        self.api_key = api_key
        self.model = model or model_for_tier("anthropic", "balanced")["id"]
        self._client = None
        if api_key:
            from anthropic import Anthropic
            self._client = Anthropic(api_key=api_key)

    def generate(self, messages, model=None, **kwargs):
        if not self._client:
            raise RuntimeError(
                "Anthropic provider has no API key configured "
                "(set ANTHROPIC_API_KEY)."
            )
        response = self._client.messages.create(
            model=model or self.model,
            max_tokens=kwargs.get("max_tokens", 1024),
            messages=messages,
        )
        parts = [block.text for block in response.content if getattr(block, "type", None) == "text"]
        text = "\n".join(parts).strip()
        usage = getattr(response, "usage", None)
        return {
            "text": text,
            "input_tokens": getattr(usage, "input_tokens", None) if usage else None,
            "output_tokens": getattr(usage, "output_tokens", None) if usage else None,
        }
