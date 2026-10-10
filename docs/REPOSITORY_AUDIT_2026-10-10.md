# Smart BethG Whole-Repository Audit

**Audit started:** 2026-10-10 UTC  
**Status:** In progress — this is a living findings register, not a final sign-off.  
**Scope:** Initial source scan of 143 Python files, 7 HTML files, 6 JavaScript files, 1 CSS file, configuration, tests, and documentation (178 tracked files at the initial tree count for this audit pass). Subsequent commits add further files. The exact reviewed revision is recorded by Git commit history on `update/corrected-zip-2026-10-10`.

## Executive assessment

Smart BethG has meaningful working components, including provider adapters, session authentication, conversation storage, file handling, owner-scoped memory, a tool authorization layer, and a test suite. However, the repository should not yet be treated as public-launch ready. Several earlier features were present only as schemas or placeholders; production PostgreSQL and cross-instance rate limiting are now being activated, but their full regression and operational verification is still required.

The most important distinction is between **code implemented**, **tests passing**, and **production operation verified**. These are different statuses. A code change or a green unit suite does not prove the live database, storage, backups, security boundary, or end-to-end browser flow is correct.

## P0 — Must resolve before public access

### P0.1 Unrestricted host execution is not a sandbox
**Finding:** The command runner previously permitted arbitrary Python code in the application process. A workspace directory alone is not an operating-system sandbox; Python code could potentially read environment secrets or access files outside the workspace. Docker CLI passthrough also allowed dangerous daemon options.

**Changes started:** Host Python execution is now disabled when `SMART_BETHG_ENV=production`; Docker commands are restricted to read-only inspection or an explicit image allowlist with a no-network, read-only, non-root, resource-limited profile. High-risk actions require approval.

**Still required:** Build a real isolated job runner for production code execution, with per-job identity, CPU/memory/time/output limits, a minimal environment, network policy, cancellation, and filesystem isolation. Independently test the Docker daemon boundary. Until then, do not expose arbitrary code execution to public users.

### P0.2 SSRF in the network tool
**Finding:** The original network tool fetched caller/model-selected URLs without blocking private or loopback targets and without a response-size cap.

**Changes started:** HTTP/HTTPS only; embedded URL credentials and non-public resolved IPs are rejected; redirects are revalidated; response bodies are capped at 2 MiB; proxy inheritance is disabled.

**Still required:** Test redirect chains, IPv4/IPv6 edge cases, DNS rebinding, timeouts, and malicious responses. The standard-library URL validation is a meaningful guard but does not pin the resolved address to the actual socket connection, so DNS rebinding is not fully eliminated. Do not claim complete SSRF immunity.

### P0.3 Approval must execute the exact operation once
**Finding:** Approval UI originally recorded a decision but did not resume the interrupted operation.

**Changes started:** The operation's action, resource/workspace, arguments, request ID, owner, and expiry are persisted. Approval decisions are owner-scoped. The service rechecks current permissions, atomically claims an approved operation, executes the saved payload, records the result, and rejects duplicate execution. The UI displays the saved arguments and execution outcome.

**Still required:** CI and end-to-end tests must verify the full route-to-tool flow, owner isolation, rejection, expiry, changed/malformed payloads, concurrent approval clicks, duplicate execution, and crash/indeterminate outcomes. An operation stuck in `running` after a process crash must not be replayed blindly; recovery/reconciliation tooling remains required.

### P0.4 Public authentication and account lifecycle
**Findings:** Registration must remain closed by default. OAuth account creation must not bypass that control. Account linking and unverified email claims can be dangerous. Password reset, account recovery, MFA, and a complete account deletion workflow are not implemented.

**Changes started:** Registration defaults closed; OAuth creation respects the registration flag; Google callback requires a verified email; an existing external identity cannot silently replace a different linked identity; OAuth callback attempts use the shared rate limiter; login clears the previous session before setting the user ID; authentication input lengths are bounded.

**Still required:** Test inactive accounts, OAuth state/error cases, registration races, brute-force behavior across replicas, CSRF, session rotation, recovery, MFA, and account deletion. Public registration must stay disabled until those gates pass.

### P0.5 Cross-user data isolation
**Finding:** Tool workspaces originally used only the workspace name, allowing users selecting the same name to share a path.

**Changes started:** Workspace roots now include the server-derived authenticated user ID; regression tests cover user separation and path traversal.

**Still required:** Audit every query and endpoint for owner scoping, especially conversation history, files, memory, knowledge chunks, provider credentials, projects, missions, artifacts, social content, and exports. Existing files from the old shared workspace layout are not automatically migrated because ownership cannot safely be inferred.

## P1 — Production architecture and reliability

### P1.1 PostgreSQL is now the production standard
**Decision:** PostgreSQL is required for production, whether one or multiple app instances run. SQLite is for local development and isolated unit tests only. Production startup fails if a PostgreSQL URL is absent.

**Changes started:** Added a PostgreSQL connection adapter, PostgreSQL schema compatibility, database-backed shared rate-limit events, a disposable PostgreSQL CI service, PostgreSQL smoke tests, and a fail-closed SQLite-to-PostgreSQL migration utility.

**Verification status:** The first PostgreSQL integration job passed its user/conversation/approval/rate-limiter smoke tests on an earlier commit. The latest code still needs a green CI run. The adapter translates the existing SQLite-oriented SQL/schema and is a migration boundary; all repository queries have not yet been proven against PostgreSQL. Add a versioned migration framework and broader PostgreSQL regression coverage before production data is trusted.

### P1.2 Single and multiple instances
**Decision:** Use the same shared PostgreSQL database and database-backed limiter in both modes.

**Open limitation:** Uploaded files, generated artifacts, and tool workspaces still use filesystem paths. Multiple app replicas must see the same durable/shared storage path, or a shared storage/workspace service must be implemented. A shared database alone does not make local files shared. Durable mission/workflow jobs and idempotent worker behavior are also required before scaling workers.

### P1.3 Token budgets and spending controls
**Finding:** Usage totals are recorded, but complete atomic per-user token/cost budgets and a global spending circuit breaker are not yet verified as enforcement before provider calls.

**Required:** Reserve estimated usage before a paid provider call, enforce per-user limits plus a global ceiling atomically in PostgreSQL, reconcile actual usage, and test concurrent requests. UI counters are not enforcement. Do not describe token budgets as complete until these tests pass.

### P1.4 Uploads, files, and storage
**Changes started:** Upload endpoint now reads at most the configured maximum plus one byte before rejecting an oversized upload. Filenames are sanitized and file records are user-scoped.

**Open issues:** Storage remains filesystem-based; file database paths must be remapped when migrating storage roots. Verify content-type handling, PDF parser limits, deletion behavior, backup coverage, and file/metadata consistency. A shared storage mount or object/workspace service is needed for multi-instance use.

### P1.5 Durable provider credentials
**Finding:** The current credential-store implementation keeps secrets in an in-memory dictionary, and provider-manager user registrations are in process memory. These will not survive restarts or synchronize across replicas. Platform provider keys are environment-driven.

**Required:** If user-supplied provider credentials are a supported product feature, store them using envelope encryption/KMS-backed key management, owner-scoped access, rotation/deletion, and audit logs. Otherwise, remove or clearly hide the incomplete user-credential feature until it is implemented.

### P1.6 Tasks, missions, workflows, and background work
**Finding:** The health service text says tasks are queued but nothing executes them, while the current task route executes work synchronously in the request path. Mission/workflow schema does not mean a durable worker exists.

**Required:** Correct health reporting, define the synchronous versus asynchronous contract, and add a durable job queue/worker with retries, cancellation, deduplication/idempotency, timeouts, and observable states before using mission/workflow automation at scale.

## P1 — Security and API findings

### P1.7 Stored XSS in the topbar
**Finding:** The topbar interpolated the user-controlled username and provider/model fields into `innerHTML`.

**Change started:** Replaced dynamic HTML construction with DOM nodes and `textContent` for account and usage data.

**Still required:** Add a browser-level XSS regression test and review all frontend sinks. Clearing an element with `innerHTML = ""` is not the same risk as inserting user-controlled strings, but all dynamic insertion sites need review.

### P1.8 CORS and route consistency
**Changes started:** CORS middleware uses the configured exact-origin allowlist. The chat router is being normalized so legacy `/api/chat` remains available and the versioned route is `/api/v1/chat`, not `/api/v1/api/chat`.

**Still required:** Verify every versioned route, error shape, CORS preflight, session/CSRF behavior, and unauthorized response in HTTP tests. CORS is not authentication and is not a CSRF defense.

### P1.9 Rate limits and abuse controls
**Changes started:** Login, registration, OAuth callback, and other authentication attempts use database-backed counters. PostgreSQL advisory locks serialize updates for the same hashed key across replicas.

**Still required:** Add limits for chat/provider calls, uploads, searches, tools, file extraction, and costly automation. Confirm trusted-proxy behavior so all users behind a reverse proxy are not accidentally treated as one IP, and do not trust arbitrary forwarded headers. Add per-user and global provider-spend limits.

### P1.10 Error handling and logging
**Finding:** The global error handler returns generic unexpected errors, but individual services may still return provider exceptions or filesystem/parser errors to users. Logs can contain provider errors, URLs, or user content. Audit event data and file-based logs need a documented retention/redaction policy.

**Required:** Standardize user-facing errors, redact secrets and sensitive prompt/file data from logs, configure retention, and verify that health endpoints do not reveal internal paths or connection strings.

## P2 — Product capabilities and maintainability

### P2.1 Schema-backed capabilities are not yet complete
The repository contains intended schema for missions, mission runs, workflows, artifacts, social content, projects, research, evidence, and files. Several corresponding model classes are empty placeholders, and some features do not yet have a complete authenticated API/service/UI/test vertical slice.

**Required implementation order:**
1. Projects and owner-scoped workspaces/files/artifacts.
2. Missions with durable state, steps, audit events, cancellation, and results.
3. Reusable workflows with validated steps, permissions, approval boundaries, and idempotency.
4. Research/evidence attached to missions with source provenance and validation.
5. Social-content drafts with review, versioning, approvals, and explicit publishing integrations.

Keep each feature unadvertised until its end-to-end flow is implemented and tested.

### P2.2 Planner and provider routing
The planner is fixed-shape rather than a general autonomous planner; this is an intentional safety choice for now. Provider auto-selection uses a simple heuristic, not a trained router. The `smartbethg_free` provider is a stub, not a working free inference service. Multi-query research and a general planner are deferred until their safety and evaluation criteria are defined.

### P2.3 User-facing management and accessibility
Knowledge/memory management, notification workflows, password reset, account deletion/export, and full settings are incomplete or partial. A full keyboard/focus/reduced-motion/screen-reader audit and browser end-to-end suite are not yet complete. The native shell has not been verified as a production mobile app.

### P2.4 Documentation and release operations
**Changes started:** Added provider-neutral setup/deployment guidance, active architecture decisions, a decision log, legal-policy drafts, and a database migration guide.

**Still required:** Independent legal review, dependency scanning, secret scanning, backups/restore drills, deployment rollback, uptime monitoring, browser QA, load tests, and a documented incident-response procedure.

## Current verification matrix

| Area | Current state | What would prove completion |
|---|---|---|
| Python unit suite | Latest run pending/needs recheck after recent changes | Latest CI job green with test count and no skips hiding required tests |
| PostgreSQL | Smoke tests passed on an earlier commit; new code needs rerun | Latest PostgreSQL CI green plus broad repository query coverage |
| Approval resume | Implemented on branch; full verification pending | End-to-end test proves exact saved action executes once and only once |
| Workspace isolation | Code/test changes added; full route audit pending | Owner-isolation tests across all resource APIs |
| CORS | Wired; test coverage added | Latest HTTP tests green with allowed and denied origins |
| Network SSRF | Initial private-IP/redirect/size guards added | Adversarial redirect/DNS tests and independent review |
| Host command execution | Python disabled in production; no real sandbox yet | Isolated runner and escape/resource-limit tests |
| Docker execution | Restricted profile added; not independently security-reviewed | Docker integration tests and daemon-boundary review |
| Persistent storage | Not verified against a live host | Write/restart/redeploy test and shared-volume test for multiple replicas |
| Backups | Not verified | Independent backup restored into a separate environment |
| Terms/Privacy | Drafts exist; not approved/published | Legal review, data-flow mapping, user consent/deletion features |
| Dependency/secret scans | Not yet added to CI | CI jobs with reviewed/remediated findings |
| Public launch | **Not approved** | All P0/P1 release gates signed off |

## Audit process and next actions

1. Finish the current CI run and fix every failing test rather than suppressing failures.
2. Review all owner-scoped endpoints and service/repository queries.
3. Add tests for the newly active PostgreSQL and approval execution behavior.
4. Complete the token/cost budget enforcement and provider credential decision.
5. Implement the planned feature vertical slices.
6. Add dependency/secret scanning, browser tests, and provider-neutral deployment smoke tests.
7. Verify storage and backup/restore on an actual test host.
8. Obtain independent security and legal review before public registration.

This document must be updated with a new timestamp and a linked commit whenever findings change status. Do not mark a finding fixed solely because code was edited; require the stated verification evidence.
