# Smart BethG Whole-Codebase Audit

**Audit date:** 2026-10-10 UTC  
**Last updated:** 2026-10-10 19:23 UTC  
**Branch reviewed:** `update/corrected-zip-2026-10-10`  
**Target branch:** `main`  
**Status:** Engineering audit in progress; public launch is not approved.  
**Scope:** Repository tree, API routing/authentication, service/repository ownership patterns, tool execution/security wrappers, database adapter/schema, CI, tests, dependencies, deployment assumptions, product capability slices, and launch documentation. This is a repository review, not an external penetration test or live-host audit.

## Executive assessment

Smart BethG has moved beyond a prototype in several important areas: the branch now has HTTP-level security tests, per-user workspace roots, persistent owner-scoped approvals, an execution path that resumes the saved approved operation, database-backed rate limiting, per-user and global usage budgets, PostgreSQL production wiring, dependency scanning, secret scanning, and dated product/legal decision documents.

The completed CI run for commit `af9f3d2c7659281c786bf994083fd2bd0da6fd22` reported **294 unit tests passing**, PostgreSQL integration tests passing (including concurrent rate-limit enforcement), dependency vulnerability audit passing, and Gitleaks secret scanning passing. The approval-decision recovery and rejection regression tests passed. GitHub Actions were also updated to Node 24-compatible action releases. These checks verify the tested branch code; they do not certify production deployment or public-launch readiness. A green CI run proves only the checks it ran; it is not a public-launch certification.

**Why the Actions page showed many red runs:** changes were committed one file at a time through the repository connector, and each intermediate commit triggered CI. Some of those intermediate commits genuinely failed while the test assertion, PostgreSQL workflow setup, and vulnerable dependency pins were being corrected. Those historical failures remain in GitHub's run history; they do not by themselves mean the latest branch head is failing. The 294-test and security-scan run for commit `af9f3d2c7659281c786bf994083fd2bd0da6fd22` is green. Any later documentation-only commit should still be checked on its current head before merge. Use the checks for the current head SHA, not an older intermediate run, to judge the current state.

## Findings by priority

### P0 — Must be closed before unrestricted public launch

**1. PostgreSQL migration/compatibility layer needs a production-grade migration strategy.**  
PostgreSQL is now the required production database, including for a single app instance. SQLite is only for local development and isolated tests. The current `database.py` adapter translates a subset of existing SQLite-style SQL and schema declarations at runtime. PostgreSQL smoke tests cover important paths, but do not prove every repository/query/schema edge case. The `executescript` translation is deliberately small and is not a substitute for versioned, reviewed schema migrations.

**Required:** introduce explicit, versioned PostgreSQL migrations; test upgrades from a clean database and a prior schema version; cover every repository with PostgreSQL integration tests; document rollback and backup/restore; do not migrate real data without a verified backup and rehearsal.

**2. Multi-instance file and workspace storage is not yet shared.**  
Database records and rate limits can be shared across replicas, but user uploads, generated artifacts, and tool workspaces still use configured local filesystem paths. A second application instance may not see a file written by the first, and a replica replacement can lose files if the host's disk is ephemeral.

**Required:** add a storage interface with a local development adapter and a production object-storage/shared-files adapter. Bind object keys to owner IDs, validate access on every operation, and test cross-instance read/write/delete. Multi-instance deployment must remain disabled until this is done.

**3. Tool execution still needs independent adversarial security review.**  
The current implementation uses a fixed tool registry, authorization policy, explicit approvals for high-risk actions, path containment checks, bounded command execution, Docker restrictions, and network URL checks. These are valuable controls, but tools can create real side effects. URL validation also has a potential DNS-rebinding gap because validation and the HTTP client's connection-time DNS resolution are separate operations. Filesystem checks should be reviewed for symlink/race behavior under concurrent access.

**Required:** independent security review; tests for DNS rebinding/redirects, symlink races, malicious Git arguments/hooks, authorization changes between approval and execution, path traversal, and cross-user access. Do not treat the existing tests as proof these attack classes are eliminated.

**4. Session revocation and account recovery are incomplete.**  
Authentication uses a signed session cookie. Logout clears the browser's cookie, but a previously copied valid cookie is not independently revocable from a server-side session store until its validity ends or the account is invalidated. A password-reset/recovery flow is not implemented.

**Required:** decide whether to move to server-side sessions or add a revocation/version mechanism; implement secure password recovery, session revocation, email/identity verification where appropriate, and abuse protection before public registration.

### P1 — Required before a responsible public release

**5. Privacy and legal documents are drafts, not approved policies.**  
Dated Terms of Service and Privacy Policy drafts now exist under `docs/`. They contain open placeholders and must match actual data flows and target jurisdictions. They are not ready to publish as final legal documents.

**Required:** identify the legal operator and contact, map all data/providers/retention/backups, define deletion/export/complaint procedures, and obtain qualified legal review. Link versioned final policies from registration and settings. Training export remains disabled until opt-in, recorded, revocable consent is implemented and tested.

**6. User data lifecycle is incomplete.**  
Per-user ownership controls exist across the reviewed project/file/memory/knowledge/artifact and other capability services, but a complete user-facing account export and deletion workflow covering conversations, uploads, artifacts, memories, research/evidence, provider records, logs, and backup-retention behavior has not been demonstrated end to end.

**Required:** build and test export/deletion as a tracked lifecycle, including related rows and stored files. Define how deletion propagates to backups and third-party providers.

**7. Browser security headers need a CSP decision and verification.**  
The application sets several security headers and can emit HSTS in production when HTTPS-only session configuration is enabled. A Content-Security-Policy is not currently configured. CSP must be designed against the actual template/script usage rather than added blindly.

**Required:** define and test a CSP, verify HTTPS and HSTS at the actual edge/host, test cookie attributes, CSRF on every unsafe cookie-authenticated route, and ensure production secrets/configuration fail closed.

**8. PostgreSQL test breadth is still limited.**  
CI now runs a real PostgreSQL service and smoke-tests user creation, conversation/message persistence, approvals, usage-budget reservation/reconciliation, and rate limiting. This is a strong start, but the complete test suite still primarily exercises SQLite.

**Required:** run service/repository suites against PostgreSQL, test concurrent budget reservations and rate-limit attempts, test schema upgrades, and test transaction rollback/error paths.

**9. Several schema-backed capabilities are not yet complete end-to-end products.**  
Projects, artifacts, missions/runs, workflows, social-content drafts, research, evidence, memory, files, and logs are intentional product areas and should be implemented—not removed merely because they are unfinished. Some current services persist and validate lifecycle records, but mission/workflow records alone do not mean a durable autonomous worker/executor or publishing integration exists.

**Required:** ship each capability as a vertical slice: owner-scoped database model/repository, service, authenticated API, usable UI, audit trail where needed, error/retry semantics, and tests. Do not advertise unfinished capabilities as fully functional.

**10. Background work needs a durable execution design before scaling.**  
Mission records and run state are persisted, but a durable worker system with leases, bounded concurrency, retries, cancellation, idempotency, and crash recovery has not been demonstrated as a complete system.

**Required:** add a durable job queue/worker abstraction backed by PostgreSQL or an appropriate queue, with explicit at-most-once/at-least-once semantics and idempotency for external side effects.

## Confirmed improvements on this branch

- PostgreSQL is now the required production backend for single-instance and multi-instance deployments; SQLite is reserved for local development and isolated tests.
- Authentication rate-limit counters are database-backed and intended to coordinate application replicas.
- Per-user and global provider-usage budgets are persisted and covered by unit/PostgreSQL tests.
- Registration is closed by default.
- CORS is wired to an exact configured origin allowlist.
- HTTP-level tests cover authentication boundaries, canonical route paths, CSRF, CORS, security headers, registration closure, and workspace separation.
- Training export is disabled pending explicit consent.
- Approval decisions are owner-scoped and persisted; the approved operation is resumed through the saved action/resource/arguments, authorization is checked again, and an atomic claim prevents duplicate execution.
- An approval-route test verifies one approved Git operation runs once. A recovery test was added to cover the narrow case where approval was persisted before execution began; it still requires a passing CI run.
- Dependency audit and Gitleaks checks are present in CI. The previous audit found vulnerable `pypdf` and `pytest` pins; these were upgraded to fixed-version ranges, and the latest completed dependency audit passed.
- Product/architecture decisions and legal drafts carry dates; the Git commit history records precise timestamps.

## Deployment portability

The application should remain provider-neutral. Render is an optional low-cost test target only, not an architectural dependency. Do not introduce required Render-specific manifests, APIs, or runtime assumptions into the application core. The portable contract is a standard Python ASGI app, explicit environment configuration, PostgreSQL, and a configured durable storage adapter.

## Recommended order of work

1. Confirm CI green after the latest approval recovery test.
2. Replace ad hoc PostgreSQL schema translation with explicit versioned migrations and broaden PostgreSQL coverage.
3. Add shared object storage while keeping a local adapter for development.
4. Complete tool-execution adversarial tests and arrange an independent security review.
5. Implement revocable sessions, password recovery, account export/deletion, CSP, and remaining privacy controls.
6. Build mission/workflow workers and complete the planned capability slices one by one.
7. Finish legal review, restore drills, monitoring, load tests, rollback tests, accessibility review, and public-launch approval.

## Verification limitations

This audit was based on the code and GitHub Actions evidence available on the named branch at the recorded date. It did not inspect live host settings, production secrets, real persistent storage, actual backups, domain/TLS configuration, provider account settings, or user traffic. Those must be verified separately. No claim is made that the application has undergone an external penetration test.
