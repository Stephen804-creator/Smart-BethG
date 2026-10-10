from .openai_provider import OpenAIProvider


class OpenRouterProvider(OpenAIProvider):
    """
    OpenRouter aggregates 190+ models behind one key, including free
    open-weight models. Its free model lineup changes frequently (it's
    tracked in their own public changelog, with entries added/removed
    on the order of weeks) - hardcoding a specific "<model>:free" ID
    here would go stale fast. Instead this defaults to "openrouter/free",
    OpenRouter's own auto-router that always resolves to *some* currently
    free model, built by them specifically to solve this problem.

    A specific model can still be requested via the chat UI's model
    picker/selection string if a user wants a named one instead of the
    auto-router - see model_catalog.py.
    """

    name = "openrouter"
    API_BASE_URL = "https://openrouter.ai/api/v1"
    CATALOG_NAME = "openrouter"
    EMBEDDING_MODEL = None  # OpenRouter has no embeddings endpoint - embed() is not usable here
    # OpenRouter asks for these for attribution on their public leaderboard -
    # optional, harmless, not a credential.
    EXTRA_HEADERS = {
        "HTTP-Referer": "https://github.com/smart-bethg",
        "X-Title": "Smart BethG",
    }
