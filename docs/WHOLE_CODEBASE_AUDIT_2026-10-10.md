# Smart BethG Whole-Codebase Audit

**Audit date:** 2026-10-10 UTC  
**Last updated:** 2026-10-10 19:36 UTC  
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

## Audit updates — 2026-10-10 19:30 UTC

### Additional defects found and addressed

**11. Invalid Font Awesome Subresource Integrity value (fixed on review branch).**  
The home page linked Font Awesome with a literal placeholder integrity="sha512-...". Browsers enforce Subresource Integrity and reject a stylesheet whose hash does not match, so icons on that page could fail to load. The placeholder attribute has been removed rather than pretending it was a real integrity hash, and a regression test now rejects this placeholder in HTML templates. Longer-term, self-hosting the required icon assets or pinning the actual verified upstream hash would reduce external-CDN dependence.

**12. Task status updates were not owner-scoped (fixed on review branch; regression test added).**  
The task repository's internal status-update method accepted a task ID without the owning user ID. There was no public status-update route in the reviewed route file, so this was a latent service/repository authorization flaw rather than a confirmed remotely exploitable endpoint. The repository update now includes both task ID and owner ID, the service requires the owner identity and validates the status allowlist, and a regression test verifies that a different user cannot change the task status.

### Verification status after these updates

The last completed security workflow for commit 6537f50e81d3a3c75af18aa7210fdf1940158951 passed both the dependency vulnerability audit and Gitleaks secret scan. The unit and PostgreSQL integration workflow for later commits was still running at the time of this update. Do not treat that earlier green security run as validation of the task-ownership changes; check the current PR head's workflow results before merge.

### UI/capability status clarification

Several schema-backed capability slices now have service, API, and unit-test coverage (projects, missions/runs, workflows, artifacts, social-content drafts, research, evidence, files, knowledge, memory). They are not all exposed through a finished user-facing workspace UI. Mission records do not yet constitute an autonomous durable worker, workflow validation does not execute workflow steps, and social-content approval does not publish to third-party platforms. Build the user-facing vertical slices and durable execution separately, and label unfinished execution honestly in the UI.

## Verification update — 2026-10-10 19:32 UTC

The unit suite caught a compatibility regression introduced while tightening task ownership: the controller was passing agent outcome labels such as executed and no_provider into a task-status allowlist that initially accepted only generic lifecycle states. The call sites were updated to include the authenticated owner, and the allowlist was expanded to the documented task outcome vocabulary. The combined CI run for commit 80aeee8e17bd7153701d735297a028f97f2651f9 then completed successfully: unit tests passed and the PostgreSQL integration job passed, including the expanded capability-service integration test. The dependency audit and Gitleaks also passed on the nearby security workflow run. A subsequent workflow-only commit updates GitHub Actions to Node 24-compatible versions; its current-head checks must still complete before merge.

## Verification and security review update — 2026-10-10 19:37 UTC

**13. PostgreSQL integer-key compatibility (fixed and covered).** The PostgreSQL schema adapter originally translated SQLite AUTOINCREMENT IDs to BIGSERIAL while related foreign-key columns remained INTEGER. The adapter now emits SERIAL for these integer ID columns, and social_content_versions is included in serial-ID handling. PostgreSQL integration coverage updates a social-content draft and verifies its version history.

**14. Approval resource and filesystem workspace normalization (fixed and covered).** Tool execution previously sanitized a workspace name for the filesystem while authorization and saved approval payloads could retain the raw input. That could make an approval describe a different resource string from the canonical directory actually used. Workspace names are now canonicalized before authorization and persistence; approved operations reject noncanonical legacy payloads and verify the saved resource matches the canonical workspace. A regression test covers traversal-like input.

**15. Concurrent PostgreSQL startup and configuration validation (covered).** PostgreSQL schema initialization is serialized with a fixed advisory lock so concurrent app workers cannot race additive schema migrations. An integration test runs multiple initializations concurrently. Configuration now rejects unknown environment names rather than silently treating a typo such as 'prod' as development; production also rejects missing or SQLite DATABASE_URL values.

**Verification as of 2026-10-10 19:36 UTC:** commit a30059deed34cd9c4ce8bcb7a693d80b713a0944 passed **303 unit tests**, PostgreSQL integration tests, dependency vulnerability auditing, and Gitleaks secret scanning. PostgreSQL coverage includes concurrent startup, cross-instance rate-limit atomicity, usage-budget persistence, and capability-service round trips. This remains repository-level verification, not an independent penetration test or proof of live-host storage/backups.


## Verification update — 2026-10-10 19:36 UTC

**Code revision verified:** `a30059deed34cd9c4ce8bcb7a693d80b713a0944` on `update/corrected-zip-2026-10-10`.

- SQLite/unit test suite: **303 tests passed**.
- PostgreSQL integration job: **passed**, including concurrent schema initialization, rate-limit concurrency, usage-budget reservation/reconciliation, conversation persistence, and capability service round trips.
- Python dependency vulnerability audit: **passed**.
- Gitleaks secret scan: **passed**.
- Python compilation: **passed**.

Additional hardening verified in this pass:
- Production environment values are explicit; unknown values such as `prod` now fail startup rather than silently selecting development behavior.
- Unit-test setup clears any inherited `DATABASE_URL` and uses a throwaway SQLite file, preventing the normal unit suite from accidentally connecting to a developer or production PostgreSQL database.
- PostgreSQL schema initialization is serialized with a session advisory lock so multiple application workers do not race through additive schema setup at startup.
- PostgreSQL-generated IDs use integer serial types compatible with the schema's integer foreign-key columns, and the social-content version-history path has PostgreSQL coverage.
- Tool authorization/approval records use the same canonical workspace name as the filesystem path, preventing the approval resource shown to a user from differing from the actual sanitized workspace.
- Approval-route regression coverage verifies that the saved Git operation resumes after approval, executes once, does not execute after rejection, and can recover when the approval decision committed before the execution claim.

These results validate the named code revision and checks above. A documentation-only audit update may create a newer Git commit; verify the resulting PR checks before merge. This is still **not** a penetration test, an independent security review, a load/chaos test, a legal sign-off, or proof of live-host configuration, persistent storage, backup restoration, domain/TLS, or monitoring.

## Current release decision

**Do not merge for unrestricted public launch yet.** The review branch has a green automated baseline, but the P0/P1 items above remain genuine launch gates. In particular, do not enable public arbitrary tool execution until an isolated production job runner and independent adversarial review exist; do not enable multiple replicas until uploads, artifacts, and workspaces use shared durable storage; and do not migrate real data until the versioned migration strategy and restore rehearsal are complete.


## Audit update — 2026-10-10 19:44 UTC

**13. Copied signed session cookies could remain valid after logout (addressed on review branch; CI pending).**  
The application used signed client-side session cookies. Clearing the browser cookie at logout did not invalidate another copy of that cookie before its expiration. Added a server-side `users.session_version` field with an additive schema migration. Password login and Google OAuth bind the cookie to the current version; authenticated and optional-user dependencies reject stale versions; logout increments the stored version, invalidating all previously issued sessions for that account. Internal session version is removed before authenticated user objects are returned to normal API handlers.

**Behavioral choice:** logging out revokes every active session for that user, not just the current browser. This is intentionally safer for a public-launch target, though it means users on other devices must sign in again.

**Verification required:** the new regression tests cover stale-cookie rejection, a current valid session, and unknown-user revocation. Do not call this closed until the CI run for the latest branch head passes. Password recovery, explicit “log out all devices,” and admin-triggered session revocation UX remain future account-management work.
