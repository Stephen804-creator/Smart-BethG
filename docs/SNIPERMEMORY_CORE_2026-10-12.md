# SniperMemory Core — Smart BethG Integration

**Created:** 2026-10-12 UTC  
**Status:** Phase 1 implementation on feature branch; review and CI required  
**Design status:** Design C remains the selected direction for continued validation. This implementation does not claim that all of Design C is complete.

## Product goal

SniperMemory is a context compiler for long-running AI work. Smart BethG keeps the complete conversation transcript for user history, but sends the model a smaller, task-specific context package: the current request, recent turns for conversational flow, relevant older turns, explicitly saved user/project/conversation memories, and relevant uploaded knowledge when available.

The goal is not to delete chat history or pretend a short context window is unlimited. It is to retrieve the useful parts instead of automatically resending every prior message.

## Phase 1 scope implemented here

- Deterministic, CPU-only retrieval using lexical relevance and inverse-document-frequency weighting.
- Recent-turn retention plus relevance-ranked older turns.
- A hard context character budget for the selected conversation turns.
- Existing explicit memory and knowledge context remain supported.
- Complete transcript persistence remains unchanged; the selector only changes what is sent to the provider.
- Basic retrieval metrics count available/selected messages and characters so tests and later telemetry can measure context reduction.
- No embedding calls, vector database, GPU, or VRAM requirement. This core can run with the same low-cost CPU footprint as the existing Python service.

## Important limits

Lexical retrieval is inexpensive but cannot reliably match every paraphrase or conceptual relationship. It may miss a fact when the user describes it with different words. Explicitly saved memories and uploaded knowledge can supplement that weakness. The next evaluation should compare retrieval against a curated set of real Smart BethG tasks and measure recall, context size, latency, and answer correctness.

This is not yet the complete Active Memory Graph from the Design C blueprint. Automatic state extraction, typed decision/constraint/task nodes, explicit relations between state nodes, AST-based code dependency indexing, and optional pgvector-backed semantic retrieval remain later, separately testable steps. They should not be added until the core selector has a measured baseline.

## Planned phases

1. **Phase 1 — compact chat context (this change):** select recent and relevant historic turns without resending the whole transcript.
2. **Phase 2 — explicit state graph:** persist user-confirmed project decisions, constraints, active tasks, and relationships with provenance, timestamps, owner/workspace scope, conflict handling, and deletion controls.
3. **Phase 3 — code/repository indexing:** parse supported languages (starting with Python AST), index symbols/imports/dependencies, retrieve target snippets and dependency snippets, and re-index changed files.
4. **Phase 4 — evaluation and optional semantic retrieval:** benchmark lexical retrieval first; add optional embeddings/pgvector only if measured recall improvements justify their cost. Keep lexical fallback and local-model compatibility.
5. **Phase 5 — standalone developer API/package:** extract stable interfaces only after Smart BethG integration is reliable and language/provider boundaries are clear.

## Design constraints

- Never send another user's history or saved memory.
- Keep the complete transcript available to the user unless they delete it.
- Do not silently invent a project decision from an assistant guess.
- Track provenance and timestamps for any future extracted state.
- Keep provider adapters independent from retrieval logic.
- Keep deployment provider-neutral; no Render-specific dependency.
- Measure token usage from provider responses where available; character count is a proxy, not an exact token count.
- No claim of infinite memory or guaranteed answer quality. Retrieval quality requires a regression corpus and end-to-end testing.

## Acceptance criteria for Phase 1

- The newest user request is always included.
- Recent turns remain available for conversational flow.
- Relevant older turns can be selected from long histories.
- Selected history remains below the configured context budget when possible.
- A long transcript is not automatically forwarded in full.
- Retrieval works without network access or paid model calls.
- Tests cover relevance, recency, context bounds, empty history, and memory ranking.
