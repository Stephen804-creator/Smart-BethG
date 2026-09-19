from .provider_base import ProviderBase


class GoogleProvider(ProviderBase):
    """Real Google Gemini provider via the `google-genai` SDK (already in
    requirements.txt).

    Gemini's API uses role "model" for assistant turns instead of
    "assistant", so incoming messages are translated before the call.
    If no key is configured, generate() raises RuntimeError rather than
    returning a fabricated response.
    """

    name = "google"

    def __init__(self, api_key: str, model: str = "gemini-2.0-flash"):
        self.api_key = api_key
        self.model = model
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
        response = self._client.models.generate_content(
            model=model or self.model,
            contents=contents,
        )
        return (response.text or "").strip()
