import config

from .smartbethg_free import SmartBethGFreeProvider
from .anthropic_provider import AnthropicProvider
from .openai_provider import OpenAIProvider
from .google_provider import GoogleProvider
from .groq_provider import GroqProvider
from .openrouter_provider import OpenRouterProvider
from .model_catalog import MODEL_CATALOG, models_for, model_for_tier, is_known_model

# Priority order used when no explicit/default provider is configured.
# Paid providers first (when configured), free/open-weight providers
# (Groq, OpenRouter) last - they're the safety net, not because they're
# lower quality, but because a user who's paying for Anthropic/OpenAI/
# Google presumably wants that one used first. If only free providers
# are configured at all, this list still "just works": the loop below
# picks whichever is actually available, so Groq/OpenRouter become the
# real default with zero special-casing - exactly the free-first setup
# someone with no paid keys ends up with.
_FALLBACK_ORDER = ["anthropic", "openai", "google", "groq", "openrouter"]


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
            self.platform["anthropic"] = AnthropicProvider(api_key=config.ANTHROPIC_API_KEY)
        if config.OPENAI_API_KEY:
            self.platform["openai"] = OpenAIProvider(api_key=config.OPENAI_API_KEY)
        if config.GOOGLE_API_KEY:
            self.platform["google"] = GoogleProvider(api_key=config.GOOGLE_API_KEY)
        if config.GROQ_API_KEY:
            self.platform["groq"] = GroqProvider(api_key=config.GROQ_API_KEY)
        if config.OPENROUTER_API_KEY:
            self.platform["openrouter"] = OpenRouterProvider(api_key=config.OPENROUTER_API_KEY)

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

    def embedding_provider_name(self):
        """
        Anthropic, Groq, and OpenRouter have no embeddings API - only
        openai/google can serve knowledge-base retrieval (T0903). None
        means "no embedding capability configured", which callers must
        treat as a real absence, not fall back to guessing at similarity.
        """
        for name in ("openai", "google"):
            if name in self.platform:
                return name
        return None

    def catalog_for_ui(self):
        """
        Only the providers/models that are actually usable right now,
        shaped for the frontend's provider+model picker.
        """
        return {
            name: {
                "label": MODEL_CATALOG[name]["label"],
                "models": models_for(name),
            }
            for name in self.available_providers()
        }

    def resolve_selection(self, selection: str | None):
        """
        Turn a UI selection ("auto", "<provider>", or "<provider>:<model_id>")
        into a concrete (provider_name, model_id) pair, honestly falling
        back to the default provider/tier when the request is invalid,
        unavailable, or absent - never raising for a bad selection.
        Returns (None, None) if nothing is configured at all.
        """
        provider_name = self.default_provider_name()
        if not provider_name:
            return None, None

        model_id = None

        if selection and selection != "auto":
            if ":" in selection:
                requested_provider, requested_model = selection.split(":", 1)
            else:
                requested_provider, requested_model = selection, None

            if requested_provider in self.platform:
                provider_name = requested_provider
                if requested_model and is_known_model(provider_name, requested_model):
                    model_id = requested_model

        if not model_id:
            tier = "balanced"
            entry = model_for_tier(provider_name, tier)
            model_id = entry["id"] if entry else None

        return provider_name, model_id

    def fallback_candidates(self, exclude=None):
        """Available providers in priority order, minus `exclude`."""
        exclude = exclude or set()
        return [name for name in _FALLBACK_ORDER if name in self.platform and name not in exclude]

    def choose_auto(self, message: str):
        """
        Smart BethG's own heuristic for "Auto" mode - NOT a learned or
        provider-side router. It looks at message length and a small set
        of complexity signals (code fences, explicit multi-step/analysis
        language) to pick a tier, then uses the configured default
        provider for that tier. This is intentionally simple and
        documented as such - it is not claimed to be more sophisticated
        than it is.
        """
        provider_name = self.default_provider_name()
        if not provider_name:
            return None, None

        tier = self._classify_tier(message)
        entry = model_for_tier(provider_name, tier)
        if not entry:
            entry = model_for_tier(provider_name, "balanced")
        return provider_name, entry["id"] if entry else None

    @staticmethod
    def _classify_tier(message: str) -> str:
        text = (message or "").strip()
        length = len(text)
        lowered = text.lower()

        complex_signals = (
            "```" in text
            or length > 600
            or any(
                kw in lowered
                for kw in (
                    "refactor", "debug", "architecture", "analyze", "analyse",
                    "step by step", "step-by-step", "compare", "design a",
                    "write a program", "algorithm", "optimi",
                )
            )
        )
        if complex_signals:
            return "capable"

        if length < 80:
            return "fast"

        return "balanced"


provider_manager = ProviderManager()
