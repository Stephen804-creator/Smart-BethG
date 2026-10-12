from .provider_base import ProviderBase
from .model_catalog import model_for_tier
import config
from services.prompt_cache import prefix_character_count


class AnthropicProvider(ProviderBase):
    """Anthropic Messages API provider with optional ephemeral prefix caching."""

    name = "anthropic"

    def __init__(self, api_key: str, model: str = None):
        self.api_key = api_key
        self.model = model or model_for_tier("anthropic", "balanced")["id"]
        self._client = None
        if api_key:
            from anthropic import Anthropic
            self._client = Anthropic(api_key=api_key)

    @staticmethod
    def _with_cache_breakpoint(messages, prefix_message_count):
        """Copy messages and mark the end of a sufficiently large stable prefix."""
        result = [dict(message) for message in messages]
        count = min(max(0, int(prefix_message_count or 0)), len(result))
        if not config.PROMPT_CACHING_ENABLED or count == 0:
            return result
        if prefix_character_count(result, count) < config.PROMPT_CACHE_ANTHROPIC_MIN_PREFIX_CHARS:
            return result

        index = count - 1
        content = result[index].get("content", "")
        if isinstance(content, str):
            result[index]["content"] = [{
                "type": "text",
                "text": content,
                "cache_control": {"type": "ephemeral"},
            }]
        elif isinstance(content, list) and content:
            blocks = [dict(block) if isinstance(block, dict) else block for block in content]
            for block_index in range(len(blocks) - 1, -1, -1):
                if isinstance(blocks[block_index], dict) and blocks[block_index].get("type") == "text":
                    blocks[block_index]["cache_control"] = {"type": "ephemeral"}
                    break
            result[index]["content"] = blocks
        return result

    def generate(self, messages, model=None, **kwargs):
        if not self._client:
            raise RuntimeError(
                "Anthropic provider has no API key configured (set ANTHROPIC_API_KEY)."
            )

        request_messages = self._with_cache_breakpoint(
            messages, kwargs.get("cache_prefix_message_count", 0)
        )
        response = self._client.messages.create(
            model=model or self.model,
            max_tokens=kwargs.get("max_tokens", 1024),
            messages=request_messages,
        )
        parts = [block.text for block in response.content if getattr(block, "type", None) == "text"]
        text = "\n".join(parts).strip()
        usage = getattr(response, "usage", None)
        return {
            "text": text,
            "input_tokens": getattr(usage, "input_tokens", None) if usage else None,
            "output_tokens": getattr(usage, "output_tokens", None) if usage else None,
            "cached_input_tokens": getattr(usage, "cache_read_input_tokens", 0) if usage else 0,
            "cache_creation_input_tokens": getattr(usage, "cache_creation_input_tokens", 0) if usage else 0,
        }
