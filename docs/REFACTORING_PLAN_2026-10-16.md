# Smart BethG Codebase Refactoring Plan

**Date:** 2026-10-16  
**Branch:** `refactor/codebase-foundation-2026-10-16`  
**Status:** Baseline reviewed; implementation proceeds in small, test-gated batches.

## Rules
- Preserve approved product behavior and PostgreSQL-only runtime architecture.
- Keep clear module boundaries; do not turn the application into a tangled monolith or split it into microservices without an explicit architecture decision.
- Inspect callers and tests before changing interfaces. No silent architecture or database changes.
- Each batch must include regression tests, documentation updates when needed, and a review of the diff. Do not claim tests passed unless they were run on that exact revision.
- Keep unfinished capabilities honest in the UI; a database table or API alone is not a finished product feature.
- Do not deploy a refactor until its branch checks pass and deployment compatibility is reviewed.

## Phases

### Phase 0 — Baseline and safety
- Confirm the target branch, current CI state, and repository/deployment mismatch.
- Record module ownership, import dependencies, configuration, database, and test boundaries.
- Avoid production behavior changes until the baseline is understood.

### Phase 1 — Application composition
- Reduce responsibilities in `main_fastapi.py` by separating app construction, middleware/security headers, router registration, and lifespan setup.
- Keep route paths, middleware order, session behavior, CSRF, CORS, and response behavior unchanged.
- Add/retain app-factory and HTTP regression tests before extracting modules.

### Phase 2 — Persistence boundaries
- Audit the PostgreSQL adapter, migration runner, repositories, transaction ownership, and SQL compatibility helpers.
- Remove duplicated persistence logic only where callers and integration tests prove equivalence.
- Add PostgreSQL tests for affected repository/service paths; never rewrite released migrations.

### Phase 3 — Service and API contracts
- Make routes responsible for HTTP validation/response mapping, services for use-case orchestration, and repositories for persistence.
- Resolve duplicate business rules and cross-layer imports one bounded feature at a time.
- Preserve owner-scoped authorization and audit behavior.

### Phase 4 — Execution and security boundaries
- Review tool registry, authorization, approvals, command execution, network access, cancellation, and audit trails.
- Fix high-risk findings with adversarial regression tests before broad restructuring.

### Phase 5 — Storage and background work
- Define a storage interface with a local adapter first; add shared durable storage only with an approved provider-neutral design.
- Design durable jobs, leases, retries, cancellation, and idempotency before enabling multiple workers/instances.

### Phase 6 — UI and capability vertical slices
- Keep frontend modules organized and accessible.
- Complete one user-facing capability at a time across UI, API, service, persistence, ownership checks, and tests.

### Phase 7 — Release verification
- Run the full unit suite, PostgreSQL integration suite, compilation, dependency audit, secret scan, browser/security tests, and deployment checks.
- Publish an evidence-based status report; passing CI is not a substitute for backup/restore, load, legal, or independent security reviews.

## First implementation target
Phase 1 starts with a test-backed extraction of application composition from `main_fastapi.py`. This is intentionally behavior-preserving. Any change to registration policy, database architecture, provider selection, or deployment behavior is out of scope for that extraction and requires its own reviewed change.


## Phase 0 findings — 2026-10-16

- The current HTTP security tests still referenced `database.DB_PATH` and attempted to switch the application back to SQLite, conflicting with the approved PostgreSQL-only runtime.
- The first refactoring batch updates those tests to use `SmartBethGTestCase`, which provisions a disposable PostgreSQL schema per test. This removes the obsolete test-only database path without changing application behavior.
- The current repository snapshot was inspected through GitHub. The test suite has **not** been executed by this refactoring pass; CI must verify this commit before the next source-code extraction.
- `main_fastapi.py` currently combines application construction, middleware definitions, template wiring, and router registration. Phase 1 will extract these responsibilities only after this test-harness alignment passes CI.
