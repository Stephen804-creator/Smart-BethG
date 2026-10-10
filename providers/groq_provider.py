from .openai_provider import OpenAIProvider


class GroqProvider(OpenAIProvider):
    """
    Groq hosts open-weight models (GPT-OSS, Qwen, Llama) on datacenter GPUs.
    Account quotas, rate limits, model availability, and any usage pricing
    depend on the current Groq plan. This reuses the OpenAI-compatible client
    but points it at Groq's endpoint and reviewed model catalog.

    Model IDs verified against Groq's own docs as of this writing;
    Groq retires models on a published deprecation schedule (they just
    retired llama-3.3-70b-versatile on 2026-08-16) - if a configured
    model starts 404ing, check console.groq.com/docs/deprecations
    before assuming something else broke.
    """

    name = "groq"
    API_BASE_URL = "https://api.groq.com/openai/v1"
    CATALOG_NAME = "groq"
    EMBEDDING_MODEL = None  # Groq has no embeddings endpoint - embed() is not usable here
