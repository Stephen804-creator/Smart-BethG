# Smart BethG Whole-Codebase Review — 2026-10-12

**Review date:** 2026-10-12 UTC  
**Reviewed baseline:** main at 7aec184064c49606e40ec66d9300b04e6198845e  
**Prompt-caching implementation:** separate branch feat/provider-prompt-caching-2026-10-12  
**Status:** Current engineering assessment; not a production certification  
**Boundary:** SniperMemory Engine / Design C is intentionally out of scope and has not been changed by this review.

## Executive conclusion

Smart BethG has a meaningful application foundation: FastAPI routes, provider adapters, PostgreSQL production direction, SQLite-based isolated unit tests, PostgreSQL integration tests, user-scoped repositories, approval workflows, tool policy, usage budgets, and CI workflows. It is still not ready for unrestricted public launch.

A critical current signal is that the most recent main-branch security workflow, run 38254113540 on 2026-10-12, failed both the Python dependency vulnerability audit and Gitleaks secret scan. The available run metadata does not establish the causes. Do not guess that these failures are harmless: inspect the full job logs, identify each finding, remediate it, and rerun the checks before treating main as release-ready.

## P0 — Resolve before public launch

### P0.1 Security workflow is red on main
**Evidence:** [Security workflow run 38254113540](https://github.com/Stephen804-creator/Smart-BethG/actions/runs/38254113540) reports failure for both “Python dependency vulnerability audit” and “Scan tracked files for secrets.”  
**Action:** Retrieve each job's complete output, distinguish actual findings from scanner/configuration errors, update or replace vulnerable dependencies where needed, and remove any real secrets from the current tree and Git history as appropriate. Do not suppress findings without documented evidence and a time-bounded exception.

### P0.2 Arbitrary code execution requires a real isolation boundary
The repository audit identifies the host Python runner as unsuitable for public users even if execution is disabled in production configuration. A workspace path is not a sandbox. Before public tool/code execution, use a separate job runner with per-job identity, filesystem isolation, CPU/memory/time/output limits, minimal environment variables, network policy, cancellation, and cleanup. Validate the Docker daemon boundary independently.

### P0.3 Network tool SSRF risk is reduced, not fully eliminated
URL checks, redirect validation, private-address blocking, response caps, and disabled proxy inheritance are useful mitigations. DNS resolution must still be bound safely to the actual outbound connection to close rebinding gaps. Test IPv4/IPv6, redirect chains, DNS rebinding, timeouts, and malformed responses before exposing the network tool publicly.

### P0.4 Authentication/account lifecycle remains incomplete
Registration is closed by default, but public launch still needs end-to-end verification of session rotation/revocation, CSRF, OAuth state and verified-email handling, account linking, brute-force protection, inactive accounts, password recovery, MFA, account deletion, and concurrent registration cases. Keep public registration closed until these gates pass.

### P0.5 Authorization requires route-by-route adversarial testing
Owner scoping has been improved, but every endpoint must be tested against a second user: conversations, files, memory, knowledge, projects, artifacts, missions, workflows, social content, provider credentials, approvals, and exports. A service-level test is not a substitute for HTTP-level cross-user tests.

### P0.6 Approval execution needs crash-safe recovery
The intended flow now persists the saved operation, revalidates authorization, atomically claims execution, records outcomes, and rejects duplicate execution. A crash after claiming an external side effect can still leave an indeterminate outcome. Never blindly replay it; implement an explicit reconciliation process and verify the complete route-to-tool path in end-to-end tests.

## P1 — Architecture and operational readiness

### P1.1 PostgreSQL and scale
PostgreSQL is the production database even for a single app instance; SQLite is local/test only. CI needs to cover more than a smoke test: all repository queries, migrations from previous schemas, concurrent reservations, transaction rollback, and backup/restore. Shared PostgreSQL and a database-backed limiter are necessary but not sufficient for multi-instance operation.

### P1.2 Files and workspaces are not automatically shared
Uploads, generated artifacts, and workspaces still depend on configured filesystem paths. Multiple replicas must use verified shared durable storage or a storage service abstraction. A shared database does not synchronize files. Verify file metadata/path consistency, deletion, backup inclusion, restore, and storage-root migration.

### P1.3 Durable jobs and mission/workflow semantics
A schema or route does not prove that a durable worker exists. Mission/workflow execution needs a durable queue, bounded concurrency, idempotency, retries, cancellation, timeout policy, recovery from crashes, and observable states. Ensure health endpoints do not claim that queued jobs are running when no worker is connected.

### P1.4 Provider credentials and local model support
The current LocalProvider is explicitly unimplemented. Do not market local model launching as functional until a supported runtime adapter, model discovery, lifecycle management, resource limits, and tests exist. The provider credential path also needs durable encrypted storage, owner scoping, rotation/revocation, and audit if user-provided API keys are a supported capability. An in-memory credential registry is not restart- or replica-safe.

### P1.5 Token/cost accounting
Per-user/global budgets should remain server-side and fail safely. Cached input tokens are currently reported separately by the interim prompt-caching branch, but the budget/cost reconciliation still uses conservative full input-token estimates. This may overestimate spend; do not use it for precise user billing until provider-specific cached-token rates and concurrency tests are implemented.

### P1.6 Model catalog accuracy
Model IDs, availability, and pricing change. Internal tests that check only catalog structure do not prove provider IDs are current or that listed pricing matches current official prices. Add a dated provider-catalog review process and a smoke test using real provider keys in a controlled environment, without putting keys in CI logs or repository files.

### P1.7 Observability, backups, and incident readiness
Before public launch, establish structured/redacted logs, error monitoring, uptime checks, operational alerts, retention limits, independent backups, and restore drills. Do not log prompts, credentials, session cookies, or private user files. Verify the real hosting configuration instead of treating README instructions as runtime evidence.

## P1 — Product and privacy readiness

- The draft Terms of Service and Privacy Policy are not approved legal documents. Reconcile them with actual data flows and have qualified counsel review them before publication.
- Map each external AI provider, search service, storage target, and connector to the data it receives and its retention/training terms.
- Training export must remain disabled until informed, recorded, revocable opt-in consent exists.
- Provide account deletion and data export with consistent deletion/retention across database rows, files, knowledge chunks, memory, artifacts, logs, and backups.
- Public launch requires a clear support/contact channel, user documentation, onboarding, abuse reporting, and an accessible user experience.

## P2 — Feature completeness and UX

- Project, artifact, mission, workflow, research/evidence, and social-content capabilities need complete user-facing vertical slices, not just API/schema presence.
- The social agent must not publish to external accounts until OAuth scopes, encrypted credentials, token refresh/revocation, ownership checks, scheduled jobs, retries, platform policy constraints, rate limits, and per-post approval/automation controls are verified.
- The local model feature, streaming responses, password recovery, complete account settings, native shell, accessibility review, and full end-to-end browser suite should be tracked as distinct deliverables rather than described as finished.
- Connectors/plugins should have a clear contract, permission model, secret lifecycle, rate limits, audit trail, and consistent failure semantics. Avoid tightly coupling the core application to one provider or deployment host.

## Interim prompt caching

A provider-native prompt-caching implementation is being prepared separately on branch feat/provider-prompt-caching-2026-10-12. It is intentionally not SniperMemory. It adds an OpenAI cache-bucketing key, an Anthropic ephemeral cache breakpoint for sufficiently large stable leading context, Gemini cached-token telemetry, and tests. It does not cache AI responses, reduce prompt length, provide local KV/VRAM caching, or guarantee savings. It remains unverified until the branch CI and live-provider checks pass. See docs/PROMPT_CACHING_2026-10-12.md.

## Release decision

**Current recommendation: do not enable unrestricted public registration or public arbitrary tool execution yet.** First resolve the failed main security checks, verify the auth/authorization boundary, complete isolated job execution and SSRF hardening, rehearse database/file backup restoration, and run an independent end-to-end security review.

A green test run is evidence for the specific tests executed; it is not proof of legal compliance, safe production infrastructure, provider billing savings, or successful recovery after a real incident.
