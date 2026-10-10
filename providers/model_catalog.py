"""
Smart BethG - Model Catalog

A dated curated list of provider model IDs, checked against official model
catalogs on 2026-10-10. Providers retire and rename models frequently; run
the model-catalog smoke checks before release and refresh this file whenever
a provider reports a model unavailable. Do not invent IDs from display names.

Each model is tagged with a "tier" used only by Auto mode:
- "fast":     cheapest/quickest, for simple, short exchanges
- "balanced": good default for most everyday requests
- "capable":  most capable, for long/complex/code-heavy requests

This tiering is Smart BethG's own judgment call, not something the
providers publish as an official ranking.
"""

MODEL_CATALOG = {
    "anthropic": {
        "label": "Anthropic",
        "models": [
            {"id": "claude-haiku-5-5", "label": "Claude Haiku 5.5", "tier": "fast"},
            {"id": "claude-sonnet-5-5", "label": "Claude Sonnet 5.5", "tier": "balanced"},
            {"id": "claude-opus-5-5", "label": "Claude Opus 5.5", "tier": "capable"},
        ],
    },
    "openai": {
        "label": "OpenAI",
        "models": [
            {"id": "gpt-6-luna", "label": "GPT-6 Luna", "tier": "fast"},
            {"id": "gpt-6.1-sol", "label": "GPT-6.1 Sol", "tier": "balanced"},
            {"id": "gpt-6-astra", "label": "GPT-6 Astra", "tier": "capable"},
        ],
    },
    "google": {
        "label": "Google",
        "models": [
            {"id": "gemini-3.5-flash-lite", "label": "Gemini 3.5 Flash-Lite", "tier": "fast"},
            {"id": "gemini-3.6-flash", "label": "Gemini 3.6 Flash", "tier": "balanced"},
            {"id": "gemini-3.1-pro-preview", "label": "Gemini 3.1 Pro (Preview)", "tier": "capable"},
        ],
    },
    "groq": {
        "label": "Groq (free, open-weight)",
        "models": [
            {"id": "openai/gpt-oss-20b", "label": "GPT-OSS 20B (Groq)", "tier": "fast"},
            {"id": "qwen/qwen3.8-27b", "label": "Qwen3.8 27B (Groq)", "tier": "balanced"},
            {"id": "openai/gpt-oss-120b", "label": "GPT-OSS 120B (Groq)", "tier": "capable"},
        ],
    },
    "openrouter": {
        "label": "OpenRouter (free, open-weight)",
        "models": [
            # OpenRouter's named free models change on the order of weeks
            # (tracked in their own public changelog). "openrouter/free" is
            # their own auto-router that always resolves to something
            # currently free, which is why it's used for all three tiers
            # here rather than three separate named models that could each
            # 404 independently. A user who wants a specific named model
            # can still type "openrouter:<exact-id>" directly.
            {"id": "openrouter/free", "label": "Auto (free, fast)", "tier": "fast"},
            {"id": "openrouter/free", "label": "Auto (free, balanced)", "tier": "balanced"},
            {"id": "openrouter/free", "label": "Auto (free, capable)", "tier": "capable"},
        ],
    },
}


def models_for(provider_name: str):
    return MODEL_CATALOG.get(provider_name, {}).get("models", [])


def model_for_tier(provider_name: str, tier: str):
    """The catalog entry for a given provider+tier, or None."""
    for m in models_for(provider_name):
        if m["tier"] == tier:
            return m
    return None


def is_known_model(provider_name: str, model_id: str) -> bool:
    return any(m["id"] == model_id for m in models_for(provider_name))
