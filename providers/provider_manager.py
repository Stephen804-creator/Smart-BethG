import config

from .smartbethg_free import SmartBethGFreeProvider
from .anthropic_provider import AnthropicProvider
from .openai_provider import OpenAIProvider
from .google_provider import GoogleProvider

# Priority order used when no explicit/default provider is configured.
_FALLBACK_ORDER = ["anthropic", "openai", "google"]


class ProviderManager:
    """
    Registry of AI providers.

    Only providers with a real API key registered here are usable.
    `smartbethg_free` remains an intentional stub (see smartbethg_free.py)
    and is never registered as usable, so callers get an honest
    "not configured" state instead of a silent crash or a fabricated
    reply.
    """

    def __init__(self):
        self.platform = {}

        if config.ANTHROPIC_API_KEY:
            self.platform["anthropic"] = AnthropicProvider(
                api_key=config.ANTHROPIC_API_KEY, model=config.ANTHROPIC_MODEL
            )
        if config.OPENAI_API_KEY:
            self.platform["openai"] = OpenAIProvider(
                api_key=config.OPENAI_API_KEY, model=config.OPENAI_MODEL
            )
        if config.GOOGLE_API_KEY:
            self.platform["google"] = GoogleProvider(
                api_key=config.GOOGLE_API_KEY, model=config.GOOGLE_MODEL
            )

        # Registered for future use once it has a real implementation.
        self._unimplemented = {"smartbethg_free": SmartBethGFreeProvider()}
        self.user = {}

    def register_user_provider(self, user_id, name, provider):
        self.user.setdefault(user_id, {})[name] = provider

    def get(self, user_id, name):
        return self.user.get(user_id, {}).get(name) or self.platform.get(name)

    def available_providers(self):
        """Names of providers that are actually usable right now."""
        return sorted(self.platform.keys())

    def default_provider_name(self):
        """The provider used for chat when the caller hasn't chosen one."""
        if config.DEFAULT_PROVIDER and config.DEFAULT_PROVIDER in self.platform:
            return config.DEFAULT_PROVIDER
        for name in _FALLBACK_ORDER:
            if name in self.platform:
                return name
        return None


provider_manager = ProviderManager()
