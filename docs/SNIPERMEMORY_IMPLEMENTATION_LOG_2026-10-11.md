# SniperMemory Implementation Log

**Created:** 2026-10-11 UTC  
**Branch:** feat/sniper-memory-core-2026-10-11  
**Base:** main at branch creation  
**Status:** Phase 1 implementation in progress; current-head CI must pass before merge.

## Initial core changes

- Added services/sniper_memory.py with deterministic local ranking and bounded context compilation.
- Added repository methods for retrieving the newest conversation window and query-matching older turns, applicable saved memories, and matching uploaded knowledge chunks.
- Integrated the context compiler into ChatService. Conversation history remains stored, but model requests use a recent window plus selected relevant evidence rather than the full history.
- Added PostgreSQL GIN full-text indexes and B-tree indexes in migration 0003_sniper_memory_search_indexes.sql; SQLite uses the existing compatible keyword path.
- Added environment settings for the context character budget and retrieval limits.
- Added regression tests for relevance ranking, owner isolation, relevant older-turn recovery, uploaded-knowledge retrieval, recent-window behavior, and context limits.

## Verification record

This log is created before the first full CI run of this branch. Do not mark tests passed until the latest branch-head unit and PostgreSQL integration workflows have completed successfully. A green test suite proves only the tested code paths, not production cost savings, retrieval recall, external security review, or live-host behavior.

## Known limits after Phase 1

- The complete active state graph is not implemented; existing explicit memories are the current saved-state source.
- AST-based repository indexing and dependency expansion are not implemented yet.
- Lexical ranking can miss semantically similar wording.
- PostgreSQL full-text indexes are production-only; SQLite's LIKE fallback is intended for development/tests and should not be used as a large-scale search backend.
- The current retrieval benchmark is a regression test suite, not yet a representative benchmark dataset.


## 2026-10-11 16:53 UTC — CI runner execution blocker

The latest observed GitHub Actions runs for commit cee600dcfe92205f9ebdde7d3cbff9dc2285cf7b are marked failed, but each job has an empty steps list, runner_id 0, and no downloadable logs. This means the jobs failed before checkout, dependency installation, compilation, or tests ran. It is not evidence of a code assertion failure, and it is also not a passing verification. Investigate repository Actions permissions/available hosted-runner capacity or retry when the runner service is available. Keep this PR unmerged until the current head has actually executed the unit and PostgreSQL integration suites.
