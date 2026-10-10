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
            {"id": "claude-haiku-5-5", "label": "Claude Haiku 5.5", "tier": "fast", "pricing_usd_per_million": {"input": 0.1, "output": 0.5}},
            {"id": "claude-sonnet-5-5", "label": "Claude Sonnet 5.5", "tier": "balanced", "pricing_usd_per_million": {"input": 2, "output": 10}},
            {"id": "claude-opus-5-5", "label": "Claude Opus 5.5", "tier": "capable", "pricing_usd_per_million": {"input": 4, "output": 20}},
        ],
    },
    "openai": {
        "label": "OpenAI",
        "models": [
            {"id": "gpt-6-luna", "label": "GPT-6 Luna", "tier": "fast", "pricing_usd_per_million": {"input": 0.1, "output": 0.5}},
            {"id": "gpt-6.1-sol", "label": "GPT-6.1 Sol", "tier": "balanced", "pricing_usd_per_million": {"input": 2, "output": 10}},
            {"id": "gpt-6-astra", "label": "GPT-6 Astra", "tier": "capable", "pricing_usd_per_million": {"input": 10, "output": 50}},
        ],
    },
    "google": {
        "label": "Google",
        "models": [
            {"id": "gemini-3.5-flash-lite", "label": "Gemini 3.5 Flash-Lite", "tier": "fast", "pricing_usd_per_million": {"input": 0.3, "output": 2.5}},
            {"id": "gemini-3.6-flash", "label": "Gemini 3.6 Flash", "tier": "balanced", "pricing_usd_per_million": {"input": 1.5, "output": 7.5}},
            {"id": "gemini-3.1-pro-preview", "label": "Gemini 3.1 Pro (Preview)", "tier": "capable", "pricing_usd_per_million": {"input": 2, "output": 12}},
        ],
    },
    "groq": {
        "label": "Groq (open-weight models)",
        "models": [
            {"id": "openai/gpt-oss-20b", "label": "GPT-OSS 20B (Groq)", "tier": "fast", "pricing_usd_per_million": {"input": 0.075, "output": 0.3}},
            {"id": "qwen/qwen3.8-27b", "label": "Qwen3.8 27B (Groq)", "tier": "balanced", "pricing_usd_per_million": {"input": 0.8, "output": 4}},
            {"id": "openai/gpt-oss-120b", "label": "GPT-OSS 120B (Groq)", "tier": "capable", "pricing_usd_per_million": {"input": 0.15, "output": 0.6}},
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
            {"id": "openrouter/free", "label": "Auto (free, fast)", "tier": "fast", "pricing_usd_per_million": {"input": 0, "output": 0}},
            {"id": "openrouter/free", "label": "Auto (free, balanced)", "tier": "balanced", "pricing_usd_per_million": {"input": 0, "output": 0}},
            {"id": "openrouter/free", "label": "Auto (free, capable)", "tier": "capable", "pricing_usd_per_million": {"input": 0, "output": 0}},
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
