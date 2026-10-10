from .provider_base import ProviderBase
from .model_catalog import model_for_tier


class OpenAIProvider(ProviderBase):
    """Real OpenAI-compatible Chat Completions provider.

    Requires the `openai` package (already in requirements.txt) and an
    API key. If no key is configured, generate() raises RuntimeError
    rather than returning a fabricated response.

    `API_BASE_URL` and `CATALOG_NAME` exist so this class can be reused
    for any OpenAI-API-compatible host (Groq, OpenRouter) by subclassing
    with a different base URL - see groq_provider.py / openrouter_provider.py.
    Those hosts use different pricing and capability limits; this class
    defaults to OpenAI's endpoint and selects a compatible token-limit
    parameter based on the provider subclass.
    """

    name = "openai"
    API_BASE_URL = None  # None = openai package's own default (api.openai.com)
    CATALOG_NAME = "openai"  # which providers/model_catalog.py entry to use
    EMBEDDING_MODEL = "text-embedding-3-small"
    EXTRA_HEADERS = None  # optional dict of default headers (e.g. OpenRouter attribution)

    def __init__(self, api_key: str, model: str = None):
        self.api_key = api_key
        self.model = model or model_for_tier(self.CATALOG_NAME, "balanced")["id"]
        self._client = None
        if api_key:
            from openai import OpenAI
            client_kwargs = {"api_key": api_key}
            if self.API_BASE_URL:
                client_kwargs["base_url"] = self.API_BASE_URL
            if self.EXTRA_HEADERS:
                client_kwargs["default_headers"] = self.EXTRA_HEADERS
            self._client = OpenAI(**client_kwargs)

    def generate(self, messages, model=None, **kwargs):
        if not self._client:
            raise RuntimeError(
                f"{self.name} provider has no API key configured."
            )
        token_limit = max(1, min(int(kwargs.get("max_tokens", 1024)), 8192))
        request_args = {
            "model": model or self.model,
            "messages": messages,
        }
        if self.name == "openai":
            request_args["max_completion_tokens"] = token_limit
        else:
            request_args["max_tokens"] = token_limit
        response = self._client.chat.completions.create(**request_args)
        text = (response.choices[0].message.content or "").strip()
        usage = getattr(response, "usage", None)
        return {
            "text": text,
            "input_tokens": getattr(usage, "prompt_tokens", None) if usage else None,
            "output_tokens": getattr(usage, "completion_tokens", None) if usage else None,
        }

    def embed(self, texts: list, task_type=None) -> list:
        """
        Real embeddings via an OpenAI-compatible embeddings endpoint -
        used for knowledge base retrieval (T0903). Raises RuntimeError
        if unconfigured, same "no fake capability" rule as generate().
        NOTE: Groq and OpenRouter do not offer an embeddings endpoint,
        so this is only actually called for the base OpenAI provider -
        see provider_manager.embedding_provider_name().
        """
        if not self._client:
            raise RuntimeError(f"{self.name} provider has no API key configured.")
        response = self._client.embeddings.create(model=self.EMBEDDING_MODEL, input=texts)
        return [item.embedding for item in response.data]
