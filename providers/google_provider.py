from .provider_base import ProviderBase
from .model_catalog import model_for_tier


class GoogleProvider(ProviderBase):
    """Real Google Gemini provider via the `google-genai` SDK (already in
    requirements.txt).

    Gemini's API uses role "model" for assistant turns instead of
    "assistant", so incoming messages are translated before the call.
    If no key is configured, generate() raises RuntimeError rather than
    returning a fabricated response.
    """

    name = "google"

    def __init__(self, api_key: str, model: str = None):
        self.api_key = api_key
        self.model = model or model_for_tier("google", "balanced")["id"]
        self._client = None
        if api_key:
            from google import genai
            self._client = genai.Client(api_key=api_key)

    def generate(self, messages, model=None, **kwargs):
        if not self._client:
            raise RuntimeError(
                "Google provider has no API key configured (set GOOGLE_API_KEY)."
            )
        contents = [
            {
                "role": "model" if m["role"] == "assistant" else "user",
                "parts": [{"text": m["content"]}],
            }
            for m in messages
        ]
        from google.genai import types
        response = self._client.models.generate_content(
            model=model or self.model,
            contents=contents,
            config=types.GenerateContentConfig(
                max_output_tokens=kwargs.get("max_tokens", 1024)
            ),
        )
        text = (response.text or "").strip()
        usage = getattr(response, "usage_metadata", None)
        return {
            "text": text,
            "input_tokens": getattr(usage, "prompt_token_count", None) if usage else None,
            "output_tokens": getattr(usage, "candidates_token_count", None) if usage else None,
        }

    EMBEDDING_MODEL = "gemini-embedding-001"

    def embed(self, texts: list, task_type=None) -> list:
        """
        Real embeddings via Gemini's embedding API - used for knowledge
        base retrieval (T0903). Raises RuntimeError if unconfigured,
        same "no fake capability" rule as generate().
        """
        if not self._client:
            raise RuntimeError(
                "Google provider has no API key configured (set GOOGLE_API_KEY)."
            )
        from google.genai import types
        embed_config = types.EmbedContentConfig(task_type=task_type) if task_type else None
        response = self._client.models.embed_content(
            model=self.EMBEDDING_MODEL,
            contents=texts,
            config=embed_config,
        )
        return [e.values for e in response.embeddings]
