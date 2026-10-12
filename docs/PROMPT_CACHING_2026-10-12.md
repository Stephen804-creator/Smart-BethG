# Interim Provider-Native Prompt Caching

**Created:** 2026-10-12 UTC  
**Last updated:** 2026-10-12 UTC  
**Status:** Implemented on a review branch; CI and live-provider verification pending  
**Scope:** Temporary cost optimization for Smart BethG's current provider adapters. This is deliberately separate from the proposed SniperMemory Engine / Design C work. Do not merge or implement SniperMemory as part of this change.

## What this feature does

Smart BethG can attach provider-supported prompt-cache hints and report cache usage returned by the provider. It does not save prompt text or AI responses in a Smart BethG cache, and it does not run a local model or maintain a local KV/VRAM cache.

- **OpenAI:** sends an opaque, HMAC-derived prompt_cache_key scoped to the user, conversation, model, and leading context. OpenAI performs prompt caching automatically when a request's prefix and model meet its cache requirements. Smart BethG reports prompt_tokens_details.cached_tokens when returned.
- **Anthropic:** adds an ephemeral cache breakpoint at the end of the leading memory/knowledge/research context only when that prefix exceeds the conservative configurable character threshold. It reports cache-read and cache-creation token counts from response usage. A cache write may cost more than ordinary input tokens; caching is not always cheaper.
- **Google Gemini:** does not create managed cache resources in this interim change. Gemini's provider-side implicit caching is automatic for supported models; Smart BethG reports cached-token usage when the SDK returns it. Cache hits are best-effort and model-specific.
- **Groq and OpenRouter:** no OpenAI-only cache parameter is sent. Their APIs and routed models differ; use provider-native behavior without assuming universal cache support.
- **Local provider:** still unimplemented. This change does not add local inference.

## Configuration

Prompt caching hints are enabled by default.

    SMART_BETHG_PROMPT_CACHING_ENABLED=true
    SMART_BETHG_PROMPT_CACHE_ANTHROPIC_MIN_PREFIX_CHARS=20000

Set SMART_BETHG_PROMPT_CACHING_ENABLED=false to disable Smart BethG's explicit Anthropic breakpoint and OpenAI cache key. This switch cannot disable automatic caching controlled internally by OpenAI or Gemini.

The Anthropic character threshold is deliberately conservative (roughly several thousand tokens depending on content). It can be adjusted for model/provider changes, but should not be lowered without checking the current provider's minimum cacheable token requirements and cache-write economics.

## Privacy and isolation

Cache keys are HMAC-derived with the application secret; raw user IDs, conversation IDs, and prompt content are not used as the key string. The key is a cache-bucketing hint, not an authorization mechanism. Prompts and any leading context still go to the selected external AI provider as part of the normal request. Provider-managed caching means the provider may retain eligible prompt prefixes under its documented cache behavior. This does not change the Privacy Policy or third-party data-processing obligations.

No prompt text is logged by this feature. Logs include only provider/model, aggregate input/output tokens, cached input tokens, and cache-creation tokens.

## Important limitations

1. **No guarantee of a cache hit.** Prefix equality, model/provider support, minimum token thresholds, timing, and provider routing determine hits.
2. **No smaller context window.** The full prompt is still submitted and counts toward model context limits. Caching reduces repeated processing cost/latency only when the provider reports a hit.
3. **No SniperMemory replacement.** This does not retrieve selected code clips, summarize chat history, build a state graph, or reduce prompt payload by design.
4. **Budgeting remains conservative.** Smart BethG's current usage budget reserves/reconciles input tokens without provider-specific cached-token price adjustments. That can overestimate cost, which is safer than undercounting, but should be improved before usage-based billing.
5. **No live billing claim yet.** Unit tests can verify request parameters and usage parsing; only real provider usage telemetry and invoices can confirm actual savings.
6. **Current context shape matters.** Explicit Anthropic caching is attached only to the leading context messages and only if those messages survive context bounding intact. If the prefix changes or is too small, the request proceeds without an explicit breakpoint.

## Verification checklist

- [ ] CI passes the unit tests and PostgreSQL integration tests on the proposed branch.
- [ ] Fake-client tests confirm provider-specific parameters, disabled mode, and cache-token parsing.
- [ ] With approved test keys, send repeated identical-context requests to each provider and confirm usage telemetry.
- [ ] Compare cache-write cost versus cache-read savings for actual model pricing and request frequency.
- [ ] Verify logs do not contain prompts, API keys, or cache contents.
- [ ] Keep the implementation on a separate review branch until the pull request is reviewed.

## Official references

- OpenAI Chat Completions API: prompt_cache_key and prompt_tokens_details.cached_tokens: https://platform.openai.com/docs/api-reference/chat/object
- Google Gemini context caching: https://ai.google.dev/gemini-api/docs/caching
- Anthropic prompt caching: https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching
