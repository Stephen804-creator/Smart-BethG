# Smart BethG Decision Log

**Maintained:** 2026-10-10 20:10 UTC
**Last updated:** 2026-10-10 20:10 UTC  
**Timestamp rule:** Each entry carries its recorded date. The exact time and author are preserved by the corresponding Git commit timestamp. New decisions are appended; superseded decisions are marked superseded rather than silently rewritten.

## 2026-10-10 — Public launch is the product target
**Status:** Active  
Smart BethG is being engineered for a public launch. Personal/small-group operation may be used during development, but it is not the intended product boundary. Public registration stays closed until the security and privacy release gates pass.

## 2026-10-10 — PostgreSQL is required in production
**Status:** Active  
PostgreSQL is the production database for both single-instance and multi-instance deployments. SQLite is permitted only for local development and isolated tests. The production app must fail fast when DATABASE_URL is missing or not PostgreSQL. This avoids building against SQLite and later having to replace the database architecture.

## 2026-10-10 — Rate limiting must be shared
**Status:** Active  
Authentication rate-limit counters are stored in the database, not only in process memory. PostgreSQL transaction-scoped advisory locks serialize the critical section for the same hashed key across replicas; the shared auth_rate_limit_locks table is retained for last-seen metadata and cleanup. A dedicated shared limiter may be considered later for very high traffic, but no production instance may rely on independent per-process counters.

## 2026-10-10 — Single and multiple app instances share one architecture
**Status:** Active, with remaining work  
Use shared PostgreSQL in both modes. Before enabling multiple app replicas, implement shared object storage for uploads/artifacts/workspace files and durable, idempotent background jobs. A shared database does not make a local filesystem shared.

## 2026-10-10 — Approval should resume the original operation
**Status:** Implemented on the review branch; recovery and adversarial review still open  
Approval is not just a notification or database status. The application persists the operation owner, action, resource, arguments, and request ID. The approval route revalidates authorization, atomically claims execution, executes the saved operation, records the outcome, and rejects duplicates. An end-to-end Git operation test passed in the latest completed test baseline; a regression test for a decision committed before execution was added afterward and awaits the next CI result. A crash after execution is claimed must not trigger blind replay; explicit operator reconciliation is still required for indeterminate side effects.

## 2026-10-10 — Build planned schema-backed capabilities
**Status:** Active  
Missions, workflows, artifacts, social content, projects, research, evidence, files, memory, and logs are intentional product areas. They are not to be left as unused tables. Implement each as a tested vertical slice (data model/repository, service, authenticated owner-scoped API, UI, audit where relevant, and tests) before advertising it as available.

## 2026-10-10 — Deployment-provider neutrality
**Status:** Active  
Render may be used as an inexpensive test target, but the application must not depend on Render-specific YAML, service types, environment assumptions, or APIs. Keep deployment configuration portable across a generic Linux/Python ASGI host, DigitalOcean, AWS, Azure, and compatible providers.

## 2026-10-10 — Legal and consent work starts now
**Status:** Active  
Draft Terms of Service and Privacy Policy now, during development, and obtain qualified legal review before public launch. Training-data use must be opt-in, recorded, and revocable; admin access is not consent. Until that consent system exists, training export remains disabled.

## 2026-10-10 — Documentation timestamps
**Status:** Active  
Architecture decisions, audit reports, migration plans, release gates, and legal drafts must carry a date/last-updated field. Changelog entries should include dates and link to the relevant commits or PR. Git commit timestamps are the precise source of truth; never invent a correction history after the fact.


## 2026-10-10 — Logout invalidates previously copied sessions
**Status:** Implemented on review branch; CI verification pending  
The signed cookie is bound to a server-side session version. Logout increments the user's version and therefore revokes all sessions issued with the previous version, across devices and replicas. This deliberately favors security over keeping other devices logged in. A stale cookie must be rejected before the route returns user data. The regression tests and current-head CI run are the verification gate.


## 2026-10-10 — Versioned PostgreSQL schema migrations
**Status:** Initial baseline implemented; upgrade and rollback verification still open  
PostgreSQL schema initialization now applies ordered SQL files under `migrations/postgresql/` and records each applied filename in `schema_migrations`. The initial baseline migration is idempotent to support a controlled adoption of databases created by the earlier schema initializer. Future schema changes must be new numbered migration files; released migrations must not be silently edited. Before production data is used, verify clean installation, adoption/upgrade from the previous schema, rollback/recovery procedure, and backup restoration.


## 2026-10-10 19:50 UTC — CI verification of session revocation and migration baseline
**Status:** Verified on review branch, not yet merged  
The revision `f805df04991a0532b1839720633c172b0f73292d` passed the 308-test unit suite, 7 PostgreSQL integration tests, Python compilation, dependency audit, and Gitleaks. The copied-cookie logout regression and idempotent PostgreSQL baseline migration test passed. This supersedes the earlier entries marked “CI verification pending” for those two implementation items. It does not close the separate launch gates for shared file storage, password recovery, full PostgreSQL repository coverage, independent security review, or backup/restore rehearsal.


## 2026-10-10 19:51 UTC — PostgreSQL upgrade regression test passed
**Status:** Verified on review branch, not merged  
Revision `3edbacc04de9e53ac1dfc9ddb8bacbd262ecab28` passed 308 unit tests, 7 PostgreSQL integration tests, Python compilation, dependency auditing, and Gitleaks. The PostgreSQL migration test now simulates a prior schema missing `users.session_version`, reapplies the unrecorded baseline, and verifies the column is restored. This is one tested upgrade path, not a replacement for full migration rehearsals and backup/restore drills.


## 2026-10-10 20:31 UTC — PostgreSQL rate-limit concurrency regression

**Status:** Fix committed to review branch; CI re-verification pending.  
A later concurrent PostgreSQL integration run exposed a real regression: 24 concurrent requests were all accepted when the configured maximum was 5. The prior lock-row upsert was not sufficient in the observed execution path. The limiter now takes a transaction-scoped PostgreSQL advisory lock keyed by the hashed limiter key before counting and inserting events. The lock is held through commit, so the critical section is serialized across replicas. The row table remains for last-seen cleanup/diagnostics, but it is no longer the sole concurrency guarantee. This issue demonstrates why a green run on an older commit must not be used as evidence for the current head.


## 2026-10-10 20:34 UTC — Global CSRF and report-only CSP

**Status:** Implemented and covered by passing current-head CI on 2026-10-10.  
All state-changing POST/PUT/PATCH/DELETE requests now require the session's CSRF token in `X-CSRF-Token`. This is a global boundary to avoid leaving newly added capability routes unprotected by omission. Browser scripts must obtain the token from `/auth/csrf` and send it for mutations. A report-only CSP is also active for observation; enforcement is intentionally deferred until violations are reviewed and inline styles are migrated.

## 2026-10-10 20:34 UTC — Project and mission dashboard vertical slice

**Status:** Implemented and covered by passing current-head CI on 2026-10-10.  
The home page now supports owner-scoped project creation/list/archive and mission creation/list through the authenticated APIs. Mission entries are tracking records only; the UI must not imply that autonomous execution exists until a durable worker is connected and tested.


## 2026-10-10 20:38 UTC — Current-head verification

**Status:** Verified on PR branch; not merged.  
Commit `022f057765f0b0ed4104f7898eeb0b95903b7a0e` passed 317 unit tests, 9 PostgreSQL integration tests, Python compilation, dashboard JavaScript syntax validation, dependency vulnerability audit, and Gitleaks secret scanning. This includes the new global CSRF regression, report-only CSP checks, project/mission dashboard HTTP owner-isolation tests, concurrent rate limiting, and concurrent user-budget reservation coverage. Production storage/backup, independent adversarial review, legal approval, and public-launch gates remain open.


## 2026-10-12 — Interim provider-native prompt caching

**Status:** Implemented on feat/provider-prompt-caching-2026-10-12; CI and live-provider verification pending.  
Smart BethG adds provider-native caching hints/telemetry while the separate SniperMemory Engine / Design C remains out of scope. OpenAI receives an opaque HMAC-derived cache-bucketing key scoped to user, conversation, model, and leading context; Anthropic gets an ephemeral cache breakpoint only for a sufficiently large stable leading context; Gemini cached-token usage is reported when available. No app-side response cache or local KV/VRAM cache is created. Full prompts are still submitted, cache hits are not guaranteed, and budget reconciliation remains conservative. See docs/PROMPT_CACHING_2026-10-12.md and docs/WHOLE_CODEBASE_AUDIT_2026-10-12.md.

## 2026-10-12 — Main-branch security workflow failure

**Status:** Open investigation; not release-ready.  
The main-branch security workflow run 38254113540 failed both the dependency vulnerability audit and the Gitleaks scan. The available run metadata did not identify the precise findings, so no cause is assumed. Retrieve the full logs, investigate each result, remediate or document evidence-based exceptions, and rerun the workflow before public release. This is independent of prompt caching and must not be hidden by a green test suite on a feature branch.
