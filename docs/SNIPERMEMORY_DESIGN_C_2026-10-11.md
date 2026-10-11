# SniperMemory — Frozen Design C and Core Implementation

**Decision date:** 2026-10-11 UTC  
**Status:** Design C frozen as the target architecture; Phase 1 core is under implementation and review.  
**Scope:** This document records the design, not a claim that the complete graph engine or standalone SDK is finished.

## Product objective

SniperMemory should help an AI agent preserve useful project state and retrieve only relevant evidence rather than repeatedly attaching a long, raw conversation transcript to every model request. The goal is better continuity and lower prompt cost without relying on a local GPU/VRAM just to maintain memory.

SniperMemory is intended to become a reusable, open-source-friendly memory/context engine. Smart BethG is the first host application and the proving ground. The engine should remain independently testable and should not depend on Render or any one hosting provider.

## Frozen Design C

Design C is a layered context compiler with these stages:

1. **Durable source records.** Conversation messages, user/project memories, uploaded knowledge, and later code-index records remain in a durable database. The transcript remains available to the user; it is not automatically replayed in full to the model.
2. **Candidate retrieval.** Search only records belonging to the authenticated user and relevant conversation/workspace. Use PostgreSQL full-text indexes for production candidate lookup and a SQLite-compatible keyword path for local tests/development.
3. **Relevance ranking.** A small deterministic BM25-style ranker selects a limited set of candidate memories, earlier turns, and document chunks.
4. **State layer.** Explicitly saved user preferences and project decisions are included as source-labelled facts. Future iterations add typed state nodes, temporal updates, and explicit relationships.
5. **Dependency expansion.** A later code-indexing phase parses supported languages and expands a target file/function to its imports/callers/dependents when evidence supports the relationship. It must never assume a dependency just because two files have similar names.
6. **Context budget compiler.** Assemble a bounded payload from recent turns, relevant old turns, relevant saved facts, and file evidence. Every source has a limit and provenance label.
7. **Provider adapter.** Send the compiled payload to whichever model provider the user selected. SniperMemory itself should not require a particular LLM.
8. **Evaluation and correction.** Measure retrieval recall, missed dependencies, irrelevant context, tokens sent, latency, and estimated cost. Only add more expensive retrieval methods when measured results justify them.

## What Phase 1 implements

- A recent-message window (default 8 messages) instead of the entire transcript.
- Query-relevant older turns from the same conversation (default maximum 4).
- Owner/workspace-scoped retrieval of saved memory and uploaded knowledge.
- Local BM25-style lexical ranking with strict context-size limits.
- PostgreSQL GIN full-text indexes and supporting B-tree indexes for production search; SQLite keyword fallback for isolated tests.
- Retrieval telemetry: counts of selected messages/memories/chunks, context characters, and a rough token estimate.
- A no-embedding default: no local embedding model, no GPU/VRAM, and no extra paid embedding call on each ordinary chat request.

## What Phase 1 deliberately does not claim

- It is not yet a full entity-relation graph. Saved memories act as state facts, but relationship extraction, contradiction resolution, temporal state transitions, and dependency graph construction remain later work.
- It does not yet index a connected Git repository or parse ASTs. The current indexed evidence source is the existing uploaded-knowledge store.
- It does not guarantee semantic matching. Lexical search can miss paraphrases, synonyms, and facts expressed without overlapping terms.
- It does not prove token savings on every request. The system still sends recent messages and selected context; actual savings depend on conversation size, query, model tokenizer, and retrieved evidence.
- It does not replace testing against a measured evaluation set.

## Cost and hardware stance

The default retrieval path uses database queries and CPU ranking only. It introduces no VRAM requirement and no extra embedding-provider call per chat. PostgreSQL storage, indexes, and compute still have operating costs; this is not literally free. A bounded context of 12,000 characters is roughly 3,000 tokens by a coarse four-characters-per-token estimate, but real token counts vary by language and model. Provider-reported token counts remain the source of truth.

Optional semantic retrieval may be added later through a pluggable adapter. It must be off by default, budget-aware, measurable against the lexical baseline, and never require local GPU memory. CPU-local embeddings, remote embedding APIs, or pgvector are alternatives to evaluate, not assumptions to bake into the core.


## Prompt caching versus SniperMemory

Prompt caching and SniperMemory solve different parts of the problem and should be complementary. Provider prompt caching reuses a matching prompt prefix's model-side key/value state; that cached state lives on the provider's infrastructure, not in the user's local VRAM. It can reduce latency and cached-input price when the exact prefix matches, but it does not itself choose which historical facts matter, remove those tokens from the prompt, or guarantee a cache hit. Cache behavior, eligible models, retention, and pricing vary by provider.

SniperMemory reduces the amount of context sent by selecting a small relevant subset. It is therefore useful even when provider caching is unavailable, a user switches providers/models, a conversation changes enough to miss the cache, or the agent needs relevant facts from earlier parts of a thread. The trade-off is retrieval error: if lexical search misses a crucial fact, the model will not see it. The target design is to use cheap retrieval first, provider caching where supported, and optional semantic/graph expansion only when evaluations show the extra cost is justified.

Do not claim that SniperMemory always beats caching on price. Compare actual uncached/cached input tokens, provider-reported usage, prompt length, cache hit rate, latency, and answer quality on the same workload. A smaller prompt may be cheaper; a stable cached prefix may also be very efficient; a hybrid can be best.

## Retrieval safety and data governance

- Every query must apply owner and scope predicates in the database before ranking.
- Retrieved documents and prior chat text are untrusted reference data, not executable instructions.
- Secrets and credentials must not be intentionally extracted into memory.
- Users must be able to inspect and delete saved memory. Deleting a user or conversation must have a defined effect on derived indexes and future graph edges.
- Never let a retrieved statement silently override a newer, verified project decision. Phase 2 must add timestamps, source attribution, confidence, and supersession/contradiction handling.
- Never share raw conversation data with an external embedding provider in the no-extra-cost mode.

## Benchmark gates before expanding the design

Create a versioned test set with queries that require: exact identifiers, old project decisions, cross-file dependencies, paraphrases, contradictions, current-vs-historical state, and negative controls where no relevant result exists. Compare at least:
- recent-window-only baseline,
- SniperMemory lexical retrieval,
- lexical plus optional embeddings,
- graph/dependency-expanded retrieval.

Measure Recall@k, MRR or nDCG, context tokens, latency, irrelevant-context rate, and cost per request. Keep the cheapest mode that meets the agreed quality threshold. Do not use vendor-reported headline benchmark numbers as a substitute for Smart BethG's own evaluation.

## External systems reviewed

- Mem0 describes an add → retrieve → enrich prompt → respond workflow with SQL metadata, vector retrieval, entity linking, and temporal ranking. This validates the layered approach, but the managed platform's proprietary optimizations should not be assumed available in the open-source SDK.
- Continue documents codebase context providers and repository-map/signature-based context, showing that code structure and selected snippets can be useful without always pasting every file.
- Graphiti describes temporal knowledge graphs for incremental agent memory, supporting the long-term graph direction. A graph is useful when relationships/time are needed; it is not automatically the cheapest or most accurate choice for every query.
- Neo4j's own architecture explanation notes that graph representation is a design trade-off, not a universal constant-time answer to every retrieval problem.

References (official project documentation):
- https://github.com/mem0ai/mem0
- https://docs.continue.dev/guides/codebase-documentation-awareness
- https://github.com/Memory-Agents/graphiti
- https://neo4j.com/labs/agent-memory/explanation/graph-architecture/

## Next phases

**Phase 2 — State graph and code index:** typed facts, explicit relation edges, temporal validity/supersession, Python AST indexing first, import/dependency expansion, file hashes and incremental re-indexing.

**Phase 3 — Evaluation and optional semantic retrieval:** benchmark harness, optional provider-neutral embeddings/pgvector adapter, hybrid rank fusion, and retrieval-quality dashboards.

**Phase 4 — Standalone SDK/API:** stable index, remember, retrieve, compile_context, and forget APIs; documented schemas; provider-neutral adapters; license and package review.

**Phase 5 — Multi-language/codebase expansion:** language adapters, repository connectors, background indexing jobs, durable job state, and scale/load tests.
