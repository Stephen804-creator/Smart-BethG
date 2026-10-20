# Smart BethG Codebase Refactoring Plan

**Date:** 2026-10-16  
**Branch:** `refactor/codebase-foundation-2026-10-16`  
**Status:** Baseline investigation in progress; structural extraction is blocked until CI failures are diagnosed and the relevant baseline is verified.

## Purpose and rationale

Smart BethG is being refactored to make responsibilities easier to locate, test,
change, and review without changing product behavior accidentally. The aim is
not to reorganize files for appearance alone: each boundary must reduce coupling
or make a security, persistence, or product contract easier to verify.

The first issue addressed is in the test foundation. Some HTTP security tests
created temporary SQLite databases by patching `database.DB_PATH` and clearing
`config.DATABASE_URL`. That approach no longer represents the supported
PostgreSQL-only runtime, can conceal PostgreSQL-specific defects, and creates a
second database path that future developers might mistakenly preserve. Those
tests now use `SmartBethGTestCase`, which provisions an isolated PostgreSQL
schema for each database-backed test and cleans it up through the shared test
harness. This improves test fidelity and isolation without changing application
runtime code.

The test workflow also now runs on pushes to every branch. Previously, the
push trigger was limited to `main`, which meant developers could not rely on a
push-triggered test run while working on a feature or refactoring branch. Pull
requests still run checks against the target branch; branch-wide push checks
provide earlier feedback during development. This change does not make a failing
check acceptable: failures must be diagnosed and fixed before the refactor is
considered verified.

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


## Implementation record

### Batch 1 — Align security tests with the supported database architecture

**Problem found:** HTTP security and approval-service tests used a temporary SQLite database by changing `database.DB_PATH` and clearing `config.DATABASE_URL`. That creates test behavior the application does not support as its runtime database architecture.

**Correction made:** The affected test classes now inherit from `SmartBethGTestCase`. The shared base provisions an isolated PostgreSQL schema for each test, so database-backed tests exercise the same database engine and adapter used by the application while remaining separated from other tests. The manual SQLite setup and teardown were removed.

**Why this matters to future maintainers:** Do not reintroduce SQLite setup or override the application's database URL in these tests. If a test needs a database, use the shared PostgreSQL test harness. This keeps the test environment representative and makes isolation/cleanup a consistent responsibility of the test base.

### Batch 2 — Make the test workflow useful on development branches

**Problem found:** The workflow's `push` trigger was restricted to `main`. Developers pushing commits to a feature or refactoring branch could not depend on the push event itself to run the suite.

**Correction made:** The branch restriction was removed from the `push` trigger, and an explanatory YAML comment now records why branch-wide testing is intentional.

**Why this matters to future maintainers:** Regression checks should run while work is being developed, not only after it reaches the main branch. A passing check is still required; broadening the trigger does not bypass any test or security requirement.

### Batch 3 — Explain the intent of security and isolation tests

The security test module now documents why it uses PostgreSQL isolation and what its key regression checks protect: security headers and report-only CSP rollout, CSRF enforcement for authenticated writes, canonical API routes, authentication on protected endpoints, operator-controlled registration, configured-origin CORS, owner-scoped approval decisions, and workspace path traversal. These comments explain the contract each test protects so a future refactor does not remove an assertion without understanding its purpose.

### Verification status and next step

The repository and workflow configuration have been inspected through GitHub. The test suite has **not** been confirmed passing. GitHub reports failed test and security checks, and the available integration did not return the failed-step logs. Therefore, the failure causes remain unverified; no claim is made that the suite passes. Retrieve the actionable CI output, fix confirmed failures, and rerun the affected tests plus the full suite before extracting application composition from `main_fastapi.py`.

The next structural target remains `main_fastapi.py`, which currently combines application construction, middleware definitions, template wiring, and router registration. Extract those responsibilities only after the test baseline is green.


## Coding standards and test quality gates

The shared engineering conventions and test strategy are documented in [`docs/ENGINEERING_STANDARDS.md`](ENGINEERING_STANDARDS.md). That document defines naming and formatting expectations, comments/docstrings that explain intent and invariants, PostgreSQL-only database testing, and the roles of unit, integration, and end-to-end tests.

Apply standards incrementally: keep touched code consistent, avoid repository-wide formatting churn, and introduce automated formatting/lint/type checks only after the current CI baseline and security findings are understood. Do not add new quality gates in a way that hides or conflates existing failures. For every failed check, capture its actual output and fix only verified causes. The current workflow logs could not be retrieved through the available GitHub integration, so the test, dependency-audit, and secret-scan failures remain unresolved and must not be described as passing.
