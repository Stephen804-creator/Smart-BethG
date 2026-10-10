# Smart BethG Production Readiness Roadmap

**Created:** 2026-10-10 UTC  
**Last updated:** 2026-10-10 UTC  
**Product target:** Public launch  
**Status:** Working roadmap; not a release approval. Exact commit timestamps are preserved in Git history.

## Executive direction

Build Smart BethG as a provider-neutral, public-facing AI agent workspace with durable files/artifacts, scheduled social campaigns, a controlled connector/plugin ecosystem, and secure tool execution. PostgreSQL is the production database even for a single application instance. The same architecture should scale to multiple instances, but horizontal scaling stays disabled until all required runtime state—not only database rows—is shared and the workers are safe.

A capability is not complete merely because its table, endpoint, or screen exists. A production slice must include: owner-scoped data, validated API, useful UI, audit trail for consequential actions, bounded timeouts/retries, durable state where work continues offline, tests, operational metrics, documentation, and recovery behavior.

## Role-by-role work and evidence

### 1. Full-stack developer

**Current evidence:** authentication/session flows, chat, projects and mission tracking, social-campaign workspace, artifact APIs/library, and connector endpoints exist across main and the current feature PR.

**Remaining work:**
- Finish the Artifact Library flow for text and bounded binary files; connect every relevant generation provider so its output is persisted as an artifact and attached to its job/mission.
- Build a complete files workspace: upload, list, download, delete, preview safe text, search, ingest into knowledge only by explicit user action, and clear size/type/retention limits.
- Build memory/knowledge management UI: inspect, edit, delete, scope, and understand what the assistant may use.
- Finish social account lifecycle, campaign calendar, per-post versions, pause/resume/cancel, publication history, failed/indeterminate jobs, and user-visible recovery guidance.
- Add robust empty/loading/error states and ensure long jobs show progress without blocking the browser.
- Add complete account settings, connected-provider management, data export/deletion, password recovery, and notifications.

**Acceptance evidence:** browser tests cover the actual user journey from login to output creation/download/deletion; no user can access another user's records or artifacts.

### 2. System / solution architect

**Active decisions:** PostgreSQL is mandatory in production for both one and many instances; SQLite is only local development/test. Deployment must remain provider-neutral. Per-user budgets plus a global spending ceiling are required. Shared database-backed rate limiting is in place.

**Remaining work:**
- Replace ad hoc SQL compatibility behavior incrementally with tested repositories and versioned PostgreSQL migrations.
- Exercise clean install, upgrade from each supported prior schema, rollback strategy, and restore from backup.
- Unify user uploads, generated artifacts, and workspaces behind explicit storage/worker interfaces. The current S3-compatible adapter covers artifacts only.
- Design remote/sandboxed workspace execution for multiple instances; a local workspace directory is not shared storage.
- Finish durable job lifecycle semantics: leases, bounded concurrency, retries, cancellation, idempotency, crash recovery, and reconciliation for external side effects.
- Define service boundaries for connectors/plugins and a capability manifest. Installing a connector must never bypass per-action permissions, budgets, approvals, or audit.
- Add architecture decision records for major trade-offs and timestamped changelog entries.

**Acceptance evidence:** a second app instance and second worker can process the same test environment without lost files, duplicate external side effects, or inconsistent authorization.

### 3. Security and data-privacy specialist

**Remaining public-launch gates:**
- Independent adversarial review of authentication, session revocation, CSRF, ownership, connector OAuth, secret vault, file paths/symlinks, network requests/redirects/DNS, Git operations, and terminal execution.
- Finish password recovery, session/account revocation, data export/deletion, consent withdrawal, and incident-reporting procedures.
- Keep registration closed until the security and operational gates are approved.
- Review data flows for every model, search service, connector, log, backup, and storage provider. Minimize prompt and file content in logs.
- Keep training export disabled until explicit opt-in, versioned consent records, withdrawal, and exclusion rules exist.
- Define encryption at rest, TLS, secret rotation, backup access controls, retention, and breach response based on verified deployment configuration.
- Enforce a tested Content Security Policy after resolving template inline styles; verify cookie attributes and HTTPS/HSTS at the actual edge.
- Run dependency and secret scans on every relevant PR; triage findings rather than merely recording them.

**Legal status:** Terms of Service and Privacy Policy are drafts. They are not legally approved or ready to publish. See docs/LEGAL_AND_PRIVACY_LAUNCH_CHECKLIST_2026-10-10.md and the dated drafts. The product owner should prepare the factual product/data-flow drafts, then obtain qualified Nigerian legal review and assess applicable Nigerian Data Protection Act/NDPC obligations and any other jurisdictions targeted. A lawyer or regulator is not a substitute for implementing the controls the documents promise.

### 4. QA engineer / tester

**Current evidence:** automated unit tests, PostgreSQL integration tests, HTTP security tests, frontend JavaScript syntax checks, dependency audit, and secret scanning run in GitHub Actions.

**Remaining work:**
- Judge the current PR-head checks, not older green or red intermediate commits.
- Increase PostgreSQL coverage across repositories and services; test migrations and transaction failures.
- Add Playwright or equivalent browser E2E flows for registration closed/open by configuration, login/logout/revocation, CSRF, project/mission creation, artifact upload/download/delete, OAuth connect/disconnect, campaign generation, approval, scheduling, pause/cancel, and publication result handling.
- Add cross-user negative tests for every route and connector/account/artifact identifier.
- Add load tests for chat, provider budgets, rate limits, uploads, artifact storage, campaign generation, and concurrent worker claims.
- Add chaos/failure tests for provider timeout, database outage, object storage outage, worker crash before/after an external side effect, expired leases, token revocation, and restore.
- Maintain a manual release checklist and record results with date, commit SHA, environment, tester, evidence, and defects.

**Acceptance evidence:** test report names the exact commit and environment; no critical/high release blocker is silently waived.

### 5. Backend developer

**Remaining work:**
- Finish the PostgreSQL repository transition and migration verification.
- Persist generation job status and artifact provenance: provider/model, output type, checksum, timestamps, source mission, and failure/retry state.
- Add a durable worker abstraction shared by mission execution and social publishing without running duplicate workers in web processes.
- Integrate generated image/audio/video outputs with artifact storage. Support larger media using streaming/multipart storage before raising current binary limits.
- Add server-side per-user/global cost and token enforcement, idempotent reservations, provider timeout handling, and cost reconciliation.
- Add connector-specific rate limits, refresh/revocation, least-privilege scopes, typed schemas, normalized errors, and audit events.
- Complete approval execution and recovery semantics for all high-risk tool actions; approvals must bind to the exact action, resource, arguments, owner, and expiry.
- Add account export/deletion, memory controls, retention cleanup, and storage quota enforcement.

### 6. Frontend / mobile developer

**Remaining work:**
- Complete responsive browser flows and PWA install/offline behavior where supported.
- Verify the UI against real API failures, expired sessions, CSRF rejection, slow provider responses, and interrupted jobs.
- Provide a usable calendar with timezone-aware schedules, edit/review states, platform/account indicators, and clear published/blocked/indeterminate statuses.
- Complete accessibility checks: keyboard navigation, visible focus, semantic labels, sufficient contrast, reduced motion, screen-reader status announcements, and useful error summaries.
- Decide the native/mobile route after the web product's core flows stabilize; do not claim native shell support until it is built and tested.

### 7. Product manager / product owner

**Decisions to validate with users:**
- Primary first user segment and the single most valuable workflow.
- What Smart BethG does better than a generic chatbot, automation platform, or social scheduling tool.
- The exact difference between assisted, approval-required, and campaign-authorized autonomous actions.
- Which connectors are launch-critical, rather than building every integration at once.
- The initial feature tier, fair usage policy, acceptable latency, data retention, support response, and refund/complaint process.

**Deliverables:** prioritized backlog with user stories, measurable acceptance criteria, launch scope, release gates, beta feedback log, and a dated changelog.

### 8. UI/UX designer

**Remaining work:** test first-time onboarding, connect-account flow, create-30-day-campaign flow, artifact discovery/download, permission/approval prompts, pause/cancel, and recovery after failed/unknown publication. Keep the social workspace focused on campaign objective, calendar, accounts, review, job status, and activity—not a cluttered duplicate chat room. Use research to validate wording and authority boundaries.

**Acceptance evidence:** usability sessions with representative target users, accessibility audit, and resolved critical confusion around what will be published, when, and on which account.

### 9. DevOps / cloud engineer

**Active direction:** portable Python/ASGI app, PostgreSQL, explicit environment configuration, optional S3-compatible storage; no Render-specific runtime dependency.

**Remaining work:**
- Provide portable local/dev/test/production environment examples with secret placeholders only.
- Build a reproducible container/deployment process and a separate supervised worker process.
- Define health/readiness checks, structured logs, metrics, alerts, restart behavior, graceful shutdown, deployment rollback, and database migration ordering.
- Configure private object storage, encryption, least-privilege service identity, lifecycle rules, and independent backups.
- Perform a PostgreSQL plus object-storage backup/restore drill; record measured recovery point/time.
- Verify TLS/domain/DNS, secrets, persistent storage, and worker supervision on the selected host. Do not claim a live environment is verified from repository code alone.
- Keep single-instance and multi-instance behavior compatible, but do not scale out until shared storage and job safety are proven.

### 10. End users

**Research needed:** interview students, developers, solo business owners, creators, and small teams before assuming all are the same audience. Observe how they connect accounts, specify a campaign, choose autonomy, review a generated post, find an artifact, recover a failure, and understand data use.

**Beta evidence:** task completion rate, time to first value, user trust in permissions, publishing accuracy, retention, support issues, and reasons users disconnect or stop paying.

### 11. Integration and distribution partners

**Potential partners to evaluate:** official AI/search providers; Meta and other social-platform developer programs; cloud/object-storage providers; GitHub; document/calendar providers; email/support systems; and payment providers.

**Requirements:** operator-owned developer apps, provider approval/review, least-privilege scopes, clear data-processing terms, revocation, rate limits, quota/cost tracking, test accounts, and end-to-end verification. A connector being listed in a catalog does not mean it is implemented or approved. Start with read-only or low-risk operations, then introduce write operations with separate permissions and audit.

### 12. Financial strategist

**Required before pricing:**
- Calculate variable cost per active user and workflow: model input/output tokens, search, storage, egress, worker compute, database, monitoring, payment fees, and support.
- Model free/trial, individual, creator/business, and team plans only after cost evidence exists. Set per-user budgets and a global platform spending ceiling; provider-side limits should be configured too.
- Estimate gross margin under low/typical/high usage and abusive workloads. Stress-test concurrent campaigns and expensive model fallback.
- Choose billing currency and payment methods with Nigerian and international users in mind, after legal/tax review. Reconcile payment webhooks idempotently and separate customer funds from operating funds.
- Set a shutdown/alert policy for spending spikes and a fair user notification path when a limit is reached.

**Acceptance evidence:** unit-economics sheet with assumptions, current provider prices, margin scenarios, monthly fixed/variable costs, and a funding/runway plan. Do not invent a profitable price before measuring usage.

### 13. Competitor and market research

**Research categories to investigate, not a claim of completed comparison:**
- General AI assistants and coding agents.
- Automation platforms and self-hostable workflow tools.
- Social scheduling/publishing platforms and creator tools.
- Agent orchestration frameworks and hosted agent platforms.
- AI media-generation tools and artifact/workspace products.

For each candidate, record current product/plan, target users, supported integrations, autonomous action controls, publishing capabilities, storage/workspace model, privacy/training policy, price, limitations, and evidence date. Use official documentation/pricing for facts and user reviews/interviews for experience signals. Validate claims before choosing positioning.

**Deliverable:** dated competitor matrix and a short positioning statement based on observed gaps—not a list of famous brands or unsupported claims.

## Release sequence

### Gate A — Core foundation
- [ ] Current PR head passes CI.
- [ ] PostgreSQL clean install and migration upgrade tests pass.
- [ ] Auth/CSRF/ownership/session-revocation tests pass.
- [ ] Artifact Library create/upload/download/delete and cross-user tests pass.
- [ ] Secrets and dependency scans pass.

### Gate B — Durable workflows
- [ ] Mission/workflow jobs have a real worker lifecycle, not only tracking records.
- [ ] Worker leases, idempotency, bounded concurrency, cancellation, and crash recovery are tested.
- [ ] Generated provider outputs are persisted as artifacts with provenance.
- [ ] Social campaign scheduling and external publication are verified with an operator-owned test account.

### Gate C — Operational readiness
- [ ] Shared object storage/workspace execution validated across two app instances.
- [ ] Backups restore successfully; rollback and incident procedures are rehearsed.
- [ ] Monitoring, alerts, load tests, chaos tests, and accessibility review complete.
- [ ] User export/deletion and retention rules verified end to end.

### Gate D — Public-launch approval
- [ ] Independent security review completed and critical/high findings addressed.
- [ ] Terms of Service and Privacy Policy reviewed by qualified counsel and linked in the product.
- [ ] Provider app approvals and data-processing terms verified.
- [ ] User research, support process, pricing/unit economics, and beta feedback reviewed.
- [ ] Product owner records a dated go/no-go decision tied to the exact release commit.

## Status rule

Do not label Smart BethG “production-ready” until Gate D is signed off. Keep historical reports immutable or append timestamped updates; do not rewrite an earlier report in a way that hides what was known at the time.
