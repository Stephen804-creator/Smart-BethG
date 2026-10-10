from .openai_provider import OpenAIProvider


class GroqProvider(OpenAIProvider):
    """
    Groq hosts open-weight models (GPT-OSS, Qwen, Llama) on real
    datacenter GPUs, free with no credit card (rate-limited, not
    token-limited the way paid APIs are). Same request/response shape
    as OpenAI, so this just points the shared client at Groq's endpoint
    with Groq's own model catalog - see model_catalog.py.

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
