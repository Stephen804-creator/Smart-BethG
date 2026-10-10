# Smart BethG Whole-Codebase Audit

**Audit date:** 2026-10-10 UTC  
**Last updated:** 2026-10-10 20:34 UTC  
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

**1. PostgreSQL migration/compatibility layer needs broader production verification.**  
PostgreSQL is now the required production database, including for a single app instance. SQLite is only for local development and isolated tests. A numbered baseline migration now exists at `migrations/postgresql/0001_initial_schema.sql`; the PostgreSQL initializer records applied migration versions in `schema_migrations` and serializes concurrent startup. The query compatibility adapter still translates a subset of existing SQLite-style repository SQL at runtime. A green PostgreSQL smoke test does not prove every repository/query/schema edge case or every upgrade from a real prior database.

**Required:** add new schema changes only as new numbered migrations; test both clean install and upgrade from a database initialized by the previous adapter; cover every repository with PostgreSQL integration tests; document rollback and backup/restore; do not migrate real data without a verified backup and rehearsal.

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

1. Confirm CI green after the latest session-revocation and versioned-migration changes.
2. Broaden PostgreSQL integration coverage to all repositories and test clean-install plus legacy-database adoption/upgrade.
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

**16. Copied signed session cookies could remain valid after logout (addressed on review branch; CI pending).**  
The application used signed client-side session cookies. Clearing the browser cookie at logout did not invalidate another copy of that cookie before its expiration. Added a server-side `users.session_version` field with an additive schema migration. Password login and Google OAuth bind the cookie to the current version; authenticated and optional-user dependencies reject stale versions; logout increments the stored version, invalidating all previously issued sessions for that account. Internal session version is removed before authenticated user objects are returned to normal API handlers.

**Behavioral choice:** logging out revokes every active session for that user, not just the current browser. This is intentionally safer for a public-launch target, though it means users on other devices must sign in again.

**Verification required:** the new regression tests cover stale-cookie rejection, a current valid session, and unknown-user revocation. Do not call this closed until the CI run for the latest branch head passes. Password recovery, explicit “log out all devices,” and admin-triggered session revocation UX remain future account-management work.


## Verification update — 2026-10-10 19:50 UTC

**Verified review-branch revision:** `f805df04991a0532b1839720633c172b0f73292d`.

- SQLite/unit CI: **308 tests completed successfully**; PostgreSQL-only tests are explicitly skipped in this job rather than accidentally running against SQLite.
- PostgreSQL integration CI: **7 tests passed**, including baseline migration tracking/idempotence, concurrent schema initialization, conversation and approval round trips, usage-budget reservation/reconciliation, database-backed rate limiting, and capability-service persistence.
- Python compilation: passed.
- Dependency vulnerability audit: passed.
- Gitleaks secret scan: passed.

The CI process caught two genuine defects during this migration work. First, the migration runner initially split a full-line SQL comment at a semicolon and tried to execute the remaining comment text as SQL; comment lines are now stripped before statement splitting, and the PostgreSQL job passes. Second, the unit-test discovery job was collecting PostgreSQL-only migration tests against SQLite; those tests now require an explicit `SMART_BETHG_RUN_POSTGRES_TESTS=1` flag that is set only in the dedicated PostgreSQL CI job. The latest tested revision is green after both corrections.

Session revocation now has unit and HTTP-level regression coverage: a copied signed session cookie works before logout and is rejected after logout increments the user's stored session version. The initial versioned PostgreSQL baseline migration is also exercised against a real PostgreSQL service and re-run idempotently.

**Remaining limits:** the query compatibility adapter remains; migration tests do not yet cover every repository or every prior production schema. Shared object storage, password recovery, complete user data export/deletion, CSP design, broad adversarial tool-security testing, independent review, backup/restore drills, load tests, and public-launch legal/security gates remain open. This green CI result is not a penetration test and does not verify live hosting, domain/TLS, storage durability, or backups.


## Verification update — 2026-10-10 19:51 UTC

**Latest code revision verified:** `3edbacc04de9e53ac1dfc9ddb8bacbd262ecab28`.

- Unit workflow: 308 tests passed; PostgreSQL-only tests are skipped here by design.
- PostgreSQL integration workflow: 7 tests passed. The migration test now goes beyond re-running the current schema: it removes the newly introduced `users.session_version` column from the disposable test database, removes the migration marker, reapplies the baseline migration, and verifies the column is restored.
- Python compilation, dependency vulnerability audit, and Gitleaks secret scan: passed.

This demonstrates one controlled prior-schema upgrade path on a disposable PostgreSQL database. It is not yet proof that every legacy production schema or every repository query migrates correctly. The original migration-parser failure and the SQLite test-discovery failure were both fixed, and the current code revision is green.


## Security audit update — 2026-10-10 20:08 UTC

**17. Network-tool DNS rebinding exposure (mitigation implemented; latest CI pending).**

The prior implementation resolved and validated a destination hostname, then passed the hostname to a standard HTTP client that could perform a second DNS lookup when opening the connection. An attacker-controlled hostname could theoretically return a public address during validation and a private/internal address during the actual connection. Redirects also require the same checks at every hop.

The review branch now uses a pinned-address HTTP(S) transport: it resolves the hostname, rejects the entire DNS answer set if any address is non-public, connects the TCP socket directly to one of the validated public IPs, and for HTTPS still verifies the certificate against the original hostname. Redirects are handled explicitly and revalidated as new destinations; proxy environment variables are not inherited. Response size, timeout, and redirect-count limits remain enforced. A regression test verifies that the connection uses the validated IP without a second DNS lookup, and existing tests cover private/mixed DNS answers and invalid permits.

**Verification state:** this finding is not marked fully closed until the unit, PostgreSQL integration, dependency-audit, and secret-scan workflows finish successfully for the exact current branch head. This mitigation reduces the DNS-rebinding risk but is not a substitute for independent adversarial testing of URL parsing, IPv6 edge cases, redirects, TLS, and the full tool-execution boundary.


## Tool-execution audit update — 2026-10-10 20:10 UTC

**18. Generic terminal execution could bypass the hardened Git wrapper (mitigation implemented; current-head CI pending).**

The generic `terminal.execute` path accepted `git` as an allowed program. Even with `shell=False`, arbitrary Git arguments can reach Git configuration and extension behavior that the dedicated `git/git_tool.py` wrapper is designed to restrict. Requiring human approval does not make an opaque or overbroad command safe by itself.

The generic command runner no longer allows raw Git commands. Git actions must use the dedicated wrapper, which disables system/global configuration, prompts, hooks, and unsafe external filters. The tool service rejects raw Git requests before creating an approval record. Host Python execution remains a development-only capability; it is rejected before approval when disabled, including in production. Tests were added for both fail-closed paths.

**Verification state:** the preceding revision passed unit tests, PostgreSQL integration, dependency auditing, and Gitleaks after the DNS-pinning mitigation. CI for the current terminal-execution change must finish successfully before this finding can be considered verified. Production terminal execution still requires a genuinely isolated worker/sandbox; this change intentionally does not pretend that the current host process is such a sandbox.


## Verification update — 2026-10-10 20:10 UTC

**Code revision verified:** `f2e8c7a97faa9ff4b41be7a8c75fdfa0ecdcc148`.

- SQLite/unit workflow: **312 tests passed**, with 7 PostgreSQL-only tests intentionally skipped in this job.
- PostgreSQL integration workflow: **passed**, including the migration-upgrade test, concurrent startup, shared rate-limit concurrency, usage-budget accounting, and capability persistence.
- Python compilation: passed.
- Dependency vulnerability audit: passed.
- Gitleaks secret scan: passed.

The new tests verify that generic raw Git terminal commands are denied before an approval record is created, and that host Python is denied before approval when development execution is disabled. The preceding DNS-pinning implementation also passed the unit, PostgreSQL, dependency-audit, and secret-scan workflows.

Subsequent commits `e877d71023817d4787751ad63633e8a6aceda204`, `ee9552496dce9c9d41db934a9c7a74e3ee6d6e1a`, and `0f6470941d8e9342476619b261323126b03cb5fe` update audit/decision documentation and timestamps only. The current branch head must still complete its own CI checks before merge; use the current head's checks, not an earlier green run, as the final gate.


## Verification correction — 2026-10-10 20:13 UTC

An intermediate PostgreSQL run exposed that the original transaction-scoped advisory-lock implementation did not reliably serialize the concurrency test: all 24 parallel attempts were accepted despite a limit of five. That was a real correctness failure, not just CI noise.

The limiter has been changed to acquire a row lock through an UPSERT in the shared `auth_rate_limit_locks` table before counting and inserting events. The table is created in SQLite development/test schema and added to PostgreSQL via the new numbered migration `0002_rate_limit_lock_table.sql`. The PostgreSQL concurrency test then passed: the tested run accepted exactly five of 24 concurrent attempts. The failed intermediate run remains in GitHub Actions history; it is superseded by the later passing run, not erased. Current branch-head CI must still finish before merge.


## Timestamped follow-up — 2026-10-10 20:30 UTC

This addendum supersedes only the older status statements explicitly corrected below; it does not erase the historical findings.

- **Current CI baseline before the CSP change:** the latest completed unit/PostgreSQL integration run and dependency/secret scans were green on commit `bb7f806234b76920afb5c185012d7544ce653653`. The CSP changes are newer, and their own runs must finish before they are called verified.
- **Session revocation:** the earlier statement that copied signed cookies could not be independently revoked is superseded by the session-version mechanism and its regression tests recorded in the decision log. Password recovery, MFA, and full account lifecycle remain open.
- **Approval resume:** the route now calls `execute_approved` for the persisted operation, atomically claims execution, rechecks current authorization, records outcome, and rejects duplicate execution. The route test covers successful Git commit, retry after a decision was recorded before execution, rejection, and duplicate protection. Crash recovery after a side effect remains a reconciliation problem; never automatically replay an operation stuck in `running`.
- **CSP:** on 2026-10-10 20:26 UTC, a `Content-Security-Policy-Report-Only` policy was added with a regression test. This is an observation phase, not enforcement. Inline styles are temporarily allowed because current templates contain style attributes and an inline style block; inline scripts and `unsafe-eval` are not allowed by the report-only policy. Review browser violation reports, migrate styles to static CSS, then enforce CSP only after compatibility testing.
- **Public-launch legal work:** dated Terms of Service and Privacy Policy remain drafts. A legal-review checklist has been added; neither draft should be represented as legally approved.
- **Public capability UI:** project, mission, artifact, workflow, social-content, research, and evidence APIs/services exist in this branch, but the home page still presents only Chat as an available capability and several features do not yet have complete user-facing workflows. API presence alone does not equal a finished product. Keep capabilities clearly labeled and do not claim autonomous mission execution or social publishing unless the actual worker/integration is implemented.
- **Production portability:** Render remains an optional test host only. The generic ASGI entry point and environment contract are documented; live deployment, storage durability, backups, and restore have not been verified from the repository.


## Timestamped follow-up — 2026-10-10 20:34 UTC

- **Shared rate-limit race found and fixed:** PostgreSQL integration CI exposed that a prior lock-row upsert accepted all 24 concurrent attempts despite a limit of 5. The limiter now acquires a transaction-scoped PostgreSQL advisory lock before counting/inserting. CI for commit `fdae607ffb4f159267297d67cd988caab9b7bdad` passed the PostgreSQL integration job, including the concurrent rate-limit regression test. A separate concurrent per-user token-budget reservation test has now been added; its latest run is pending.
- **CSRF protection broadened:** a global ASGI middleware now checks the session CSRF token on every POST, PUT, PATCH, and DELETE route, rather than relying only on route-by-route protection for authentication endpoints. A regression test proves an authenticated project creation is rejected without the token and accepted with it. This must be verified on the latest CI head; browser flows and all external API clients still need compatibility testing.
- **Content Security Policy:** report-only CSP and header tests are committed. This is deliberately not yet enforcement; review browser violation reports and remove inline styles before moving to an enforced policy.
- **Project/mission dashboard:** the home page now has authenticated project creation/list/archive and mission-recording/list workflows. A project/mission HTTP test checks owner isolation and rendered controls. The UI explicitly states mission records are tracking data only; there is still no autonomous mission worker.
- **Current-head verification rule:** commits `874dadc16e91e11721acaafd44ff3ccf270a7f48` and `9aa15aac89c4e340814be9525688a064f6eb51f9` had a dashboard test assertion that looked for wording in the rendered HTML even though that wording was only in the external JavaScript. The assertion was corrected on the later branch head. Those historical failures must not be confused with the final result; wait for the current-head test and PostgreSQL jobs before calling this batch green.
- **Legal:** the Terms and Privacy files remain drafts. The dated legal checklist now explains the difference between the NDPC regulator, a qualified technology/privacy lawyer, and a licensed DPCO. No legal approval is claimed.
