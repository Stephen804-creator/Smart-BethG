# Smart BethG — Roadmap

Source: approved roadmap section of the feature specification. These are
committed future capabilities, not rejected merely because they were too
complex for V1. See `idea.md` for uncommitted possibilities and
`v1_capabilities.md` for the current build target.

## Approved roadmap features

### Creation

-   Full website builder
-   Full web-app generation
-   Mobile-app generation
-   Full software/application generation
-   Rich presentation generation
-   Advanced document production
-   Advanced image generation
-   Advanced video/media generation
-   Larger multimedia workflows

### Automation

-   Broader workflow automation
-   Scheduled tasks
-   Recurring tasks
-   Cross-application workflows
-   External actions
-   Browser/computer control
-   More autonomous execution
-   Advanced recovery and verification

### Integrations

-   Email
-   Cloud storage
-   Productivity suites
-   Project-management systems
-   Business platforms
-   Communication platforms
-   Broader connector/plugin ecosystem

### Intelligence

-   Deeper research
-   Larger project knowledge
-   Stronger persistent memory
-   More advanced data analysis
-   Specialized domain agents
-   Multi-agent orchestration

### Collaboration and deployment

-   Team workspaces
-   Permissions
-   Shared artifacts
-   Collaboration
-   Deployment workflows
-   Monitoring and maintenance of generated applications

## Foundation completion backlog (tracked, not yet complete)

These are separated from the approved feature roadmap so current capabilities are
not overstated. A roadmap entry is not evidence that a feature is implemented.

### Unit 2 — Shared storage and multi-instance readiness
- [ ] Inventory every filesystem read/write path for uploads, artifacts, research,
  projects, social content, missions, workflows, logs, exports, and temporary files.
- [ ] Use scripts/migrate_local_storage.py to migrate existing database-referenced
  uploads/artifacts to shared storage. Dry-run first; keep local sources until
  backup, restore, and rollback are verified.
- [ ] Migrate other durable paths only after the inventory identifies live code,
  database references, and ownership rules. Do not migrate unused directory
  declarations just because they exist in configuration.
- [ ] Verify cross-instance read/write/delete, missing-object recovery, orphan
  cleanup, backup/restore, and rollback against a disposable test bucket.

### Unit 3 — Advanced memory
- [ ] Add provider-backed semantic retrieval with explicit budget reservation,
  embedding-model versioning, and keyword fallback. Do not incur provider cost
  unless configured policy permits it.
- [ ] Expand conflict detection beyond conservative polarity/numeric signals;
  preserve provenance and request confirmation instead of silently resolving
  ambiguous conflicts.
- [ ] Add versioned memory consolidation/deduplication with preview, audit trail,
  and user approval before merging or deleting memories.

### Unit 4 — Knowledge retrieval and evidence
- [ ] Add OCR for image-only PDFs and supported image uploads with runtime
  dependency checks and page/pixel/time limits.
- [ ] Evaluate reranking against a labelled retrieval-quality test set before
  adopting a more expensive reranker.
- [ ] Add independent external-source verification through approved connectors,
  recording source identity, URL, retrieval time, and outcome.
- [ ] Improve source disagreement analysis and claim-to-citation coverage; never
  treat a disagreement heuristic as proof that either source is correct.


## Numbered implementation status — Units 5–9 (2026-10-24)

### Unit 5 — Typed capability registry
- [x] Trusted code-defined capability contracts, argument validation, risk labels, and permission identifiers added as a prerequisite for connector dispatch.
- [ ] Broader developer SDK and external schema versioning remain future work.

### Unit 6 — External connector platform
- [x] Owner-scoped connector catalog/installations, permission grants, adapter interface, and safe built-in knowledge-search adapter.
- [x] OAuth authorization flows, one-time state validation, Google PKCE, encrypted per-installation credentials, and live GitHub/Drive/Slack adapter implementations added.
- [x] Provider adapter availability is distinguished from provider OAuth app configuration; credentials are not exposed through installation APIs.
- [ ] Provider sandbox/end-to-end tests and operator-managed KMS/secret-manager integration remain production hardening tasks.

### Unit 7 — Connector-aware approval and policy
- [x] Fail-closed policy checks, read-only versus side-effecting classification, persisted approval payloads, revalidation, and single-claim execution.
- [x] Legacy direct host-side actions remain blocked.
- [ ] Adversarial race/recovery tests and provider-specific scope validation remain launch gates.

### Unit 8 — Durable jobs and workers
- [x] PostgreSQL queue, idempotency keys, priority, leases, guarded completion, bounded retry/backoff, owner-scoped status and cancellation APIs.
- [x] Worker is a separate process, not an in-process web-server background task.
- [ ] Multi-worker crash/replay tests and operational monitoring remain required before horizontal scaling.

### Unit 9 — Mission execution engine
- [x] Missions can store validated, bounded connector-action plans and enqueue runs atomically with run creation.
- [x] Worker executes registered steps, persists progress, pauses side-effecting steps for approval, and resumes after approval.
- [ ] Mission planning from natural language, compensation/saga recovery, and end-to-end external provider tests remain future work.

Status is implementation status, not a claim that live external provider integrations or multi-instance production readiness have been verified.


## Numbered implementation status — Units 10–15 (2026-10-25, implementation follow-up)

### Unit 10 — Reusable workflow execution
- [x] Durable workflow-run and per-step records, atomic child-mission/step creation, sequential step dispatch, completion aggregation, and step-index-bound queue messages.
- [x] Mission, research-record, artifact, and social-content-draft steps execute through existing trusted services. Social-content steps create drafts only and never publish externally.
- [x] Child mission completion advances the parent workflow and queues the next step in the same database transaction.
- [x] Bounded condition steps support earlier-step result paths, explicit comparison operators, and guarded downstream step skipping.
- [x] Internal research, artifact, and social-draft adapters use stable per-step idempotency keys, allowing safe recovery after a crash between record creation and workflow-step completion; unsupported or external side effects fail closed.
- [ ] Compensation/saga rollback, live publishing adapters, and automatic recovery from ambiguous external side-effect outcomes remain open.

### Unit 11 — Specialist coordination
- [x] Role-specific specialist calls run sequentially through ChatService, persist each contribution, pass prior contributions as context, and use role-specific capability-tier preferences when configured catalog routes are available.
- [x] Specialist calls use the existing chat budget reservation/reconciliation path; results are stored and recorded in the decision ledger.
- [x] Ambiguous interrupted provider calls fail closed to avoid duplicate billable calls.
- [x] Role-specific tier preferences use the shared cost-aware router when catalog routes are available; critic and reviewer prompts provide basic challenge/synthesis behavior.
- [ ] Explicit per-role provider overrides, a dedicated inter-agent message bus, deterministic arbitration, and safe automatic retry after ambiguous provider outcomes remain open.

### Unit 12 — Decision ledger and execution evidence
- [x] Owner-scoped bounded decision records with optional mission/workflow references.
- [x] Workflow step outcomes and specialist result metadata are automatically recorded with evidence references.
- [ ] Complete instrumentation of every policy/provider/approval decision and enforced immutable retention/archival policy remain open.

### Unit 13 — Agent evaluation
- [x] Versioned deterministic checks, owner-scoped evaluation records, human-labelled outcomes, and empirical Brier/MAE calibration diagnostics.
- [x] Calibration responses explicitly report insufficient data until at least 10 labelled examples are available.
- [ ] A reviewed, versioned human-labelled benchmark corpus, larger regression suite, statistically meaningful calibration data, and independent factuality evaluation remain open.

### Unit 14 — Cost-aware model routing
- [x] Authenticated route preview estimates costs for configured catalog entries and records the preview decision.
- [x] Existing synchronous ChatService calls already reserve budgets before provider calls, reconcile known usage, retain conservative reservations on unknown usage, and record latency/provider outcomes.
- [x] Auto chat selection uses the cost-aware route preview; provider calls still reserve/reconcile usage through ChatService.
- [x] Route ranking uses observed success rate and latency after at least five calls per model; actual route and fallback outcomes are recorded in the decision ledger.
- [ ] Provider catalog live smoke checks remain open; no provider keys or live API smoke calls were used as part of this change. Mission workflow steps currently create records/artifacts/drafts or dispatch missions; they do not perform hidden AI generation.

### Unit 15 — Account recovery and data lifecycle
- [x] Owner-scoped JSON export with schema version, export manifest, nested sensitive-key filtering, row/size limits, and explicit omission/truncation reporting. Operational logs are explicitly excluded and disclosed in the manifest.
- [x] Owner-scoped lifecycle request records for data export and account deletion.
- [ ] Verified recovery delivery, identity verification and confirmation flow, safe deletion execution, retention schedule enforcement, and legal/privacy approval remain open. Deletion is not automatic.

These are implementation states for the PR #17 follow-up branch, not a production launch approval. Provider sandbox testing, multi-worker crash/replay testing, deployment-specific recovery configuration, and full legal/privacy review remain required.


## Numbered implementation status — Units 16–20 (2026-10-26)

### Unit 16 — Organizations and workspace permissions
- [x] PostgreSQL organizations, organization memberships, workspaces, and workspace memberships with role validation.
- [x] Owner/admin member management, inherited organization-admin workspace access, and fail-closed access checks.
- [x] Owner roles cannot be demoted or removed through ordinary member-management endpoints; organization membership revocation also removes workspace grants atomically.
- [ ] Bind legacy projects, missions, workflows, artifacts, files, research, evidence, and social content to workspaces and audit every resource read/write path. Until then, existing resources remain user-owner-scoped and are not automatically shared with workspace members.

### Unit 17 — Sandboxed execution environment
- [x] Added an opt-in Python runner through Docker with fixed interpreter, no network, read-only source mount/root filesystem, dropped capabilities, non-root user, process/memory/CPU limits, bounded output, timeout, and run records.
- [x] Execution fails closed unless the exact image reference contains a complete 64-hex SHA-256 digest and is present in the operator allowlist; timeout cleanup attempts both kill and forced removal.
- [ ] Build/review the production image and test adversarial workloads against the real Docker daemon; rootless/dedicated runner isolation and operational testing remain launch gates.

### Unit 18 — Social content creation and publishing
- [x] Approved drafts can be scheduled with timezone validation, idempotency keys, listing, cancellation, and due-job processing.
- [x] Unconfigured or ambiguous external publication is marked blocked; it is never reported as published and is not blindly retried.
- [ ] No Facebook, Instagram, LinkedIn, YouTube, X, or blog publisher is registered by this unit. Implement and validate platform-specific OAuth, scopes, rate limits, token lifecycle, and real sandbox/account posting before claiming external publishing is available.

### Unit 19 — Monitoring, tracing, and operational observability
- [x] Request IDs are returned and logged; bounded low-cardinality request metrics are persisted without bodies, cookies, query strings, or raw resource IDs.
- [x] Worker process publishes database-backed heartbeats; health checks report actual heartbeat status.
- [x] Admin-only metrics endpoint reports request totals, errors, latency aggregates, route summaries, and active worker heartbeats.
- [ ] External log/trace export, alerting, load testing, queue-lag dashboards, and retention operations need deployment-level validation.

### Unit 20 — Production security, recovery, and launch gates
- [x] Admin-only readiness checks cover database/migrations, worker liveness, persistent session secret, secure cookies, backup/restore attestation, and sandbox image configuration.
- [x] Added a production launch checklist for backups, schema rehearsal, shared storage, sandboxing, social publishers, monitoring, and security/privacy review.
- [ ] A successful restore drill, security review, live deployment configuration, CSP enforcement decision, and legal/privacy approval are not performed by this code change. `SMART_BETHG_BACKUP_RESTORE_VERIFIED=true` is an operator attestation, not automated proof.

See `docs/UNITS_16_20_IMPLEMENTATION.md` and `docs/PRODUCTION_LAUNCH_CHECKLIST_2026-10-26.md`. These are implementation foundations, not production launch approval.


## Numbered implementation status — Units 21–24 (2026-10-27)

### Unit 21 — Scheduled and recurring agent jobs
- [x] Owner-scoped one-off/recurring schedules for validated workflows, with bounded intervals and run counts.
- [x] Durable queue dispatch with transactional schedule occurrence/workflow-run linkage and idempotency keys.
- [ ] Cron calendar/timezone UI, notifications, compensation, and production multi-worker crash/replay drills remain open.

### Unit 22 — Capability extensions and developer SDK
- [x] Python SDK builder for versioned declarative extension manifests and typed action contracts.
- [x] Owner-scoped draft manifests with explicit admin approval/disable state; arbitrary extension code is never executed.
- [ ] Trusted adapter implementation, extension signing/distribution, developer portal, and third-party runtime certification remain open.

### Unit 23 — Usage intelligence and fairness
- [x] Private account usage summaries for tokens, estimated spend, model/provider usage, and daily capacity.
- [x] Plan-aware daily request caps enforced through an atomic PostgreSQL counter in the usage reservation transaction.
- [ ] Provider invoice reconciliation, anomaly alerts, team allocation policies, and load/concurrency verification remain open.

### Unit 24 — Plans, credits, rewards, and retention foundations
- [x] Free/Starter/Pro/Team plan metadata, admin plan assignment, idempotent credit ledger, and non-negative transactional debits.
- [x] Reward requests require admin review before credits are issued.
- [ ] Checkout, payment/webhook integration, automatic monthly credit allocation, referral abuse controls, and legal/tax review remain open.

See docs/UNITS_21_24_IMPLEMENTATION.md. The code is not a production launch approval; CI and deployment-specific verification remain required.
