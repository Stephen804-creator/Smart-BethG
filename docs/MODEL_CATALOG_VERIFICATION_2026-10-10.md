# Provider Model Catalog Verification

**Verified:** 2026-10-10 UTC  
**Status:** Catalog corrected against official provider pages; recheck before releases.

## Anthropic
Current catalog IDs used here:
- `claude-haiku-5-5`
- `claude-sonnet-5-5`
- `claude-opus-5-5`

Official source: https://platform.claude.com/docs/en/models/overview

## OpenAI
Current catalog IDs used here:
- `gpt-6-luna`
- `gpt-6.1-sol`
- `gpt-6-astra`

Official source: https://platform.openai.com/pricing/

## Google Gemini
Current catalog IDs used here:
- `gemini-3.5-flash-lite`
- `gemini-3.6-flash`
- `gemini-3.1-pro-preview`

Official source: https://ai.google.dev/gemini-api/docs/models

## Groq
Current catalog IDs used here:
- `openai/gpt-oss-20b`
- `qwen/qwen3.8-27b`
- `openai/gpt-oss-120b`

Official source: https://console.groq.com/docs/models

## OpenRouter
The catalog uses the provider's `openrouter/free` auto-router. Verify that this model alias remains supported and that the selected upstream model's data handling and pricing match the user's expectations before production use.

Official source: https://openrouter.ai/docs

## Important behavior note
A model appearing in the catalog does not prove the configured account/key can call it, that it is available in the user's region, or that the provider API accepts the request parameters used by Smart BethG. The live provider smoke test must run with operator-controlled test credentials before public launch. Never store those credentials in CI or commit them.
