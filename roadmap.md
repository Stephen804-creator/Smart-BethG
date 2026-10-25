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
- [x] Replay of already-claimed side-effecting non-mission steps fails closed rather than blindly repeating a potentially completed side effect.
- [ ] Conditional branching, compensation/saga recovery, live publishing adapters, and automated recovery from an ambiguous side-effect outcome remain open.

### Unit 11 — Specialist coordination
- [x] Role-specific specialist calls run sequentially through the configured ChatService provider, persist each contribution, and pass prior contributions as context.
- [x] Specialist calls use the existing chat budget reservation/reconciliation path; results are stored and recorded in the decision ledger.
- [x] Ambiguous interrupted provider calls fail closed to avoid duplicate billable calls.
- [ ] Specialists are not independently routed to distinct providers/models; robust inter-agent message protocols, arbitration, and resumable per-role retries remain open.

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
- [x] Auto chat selection uses the cost-aware route preview to choose among configured catalog entries; provider calls still reserve/reconcile usage through ChatService.
- [ ] Provider catalog live smoke checks and latency/reliability-informed routing remain open. Mission workflow steps currently create records/artifacts/drafts or dispatch missions; they do not perform hidden AI generation.

### Unit 15 — Account recovery and data lifecycle
- [x] Owner-scoped JSON export with schema version, export manifest, sensitive-column filtering, row/size limits, and explicit omission/truncation reporting.
- [x] Owner-scoped lifecycle request records for data export and account deletion.
- [ ] Verified recovery delivery, identity verification and confirmation flow, safe deletion execution, retention schedule enforcement, and legal/privacy approval remain open. Deletion is not automatic.

These are implementation states for the PR #17 follow-up branch, not a production launch approval. Provider sandbox testing, multi-worker crash/replay testing, deployment-specific recovery configuration, and full legal/privacy review remain required.
