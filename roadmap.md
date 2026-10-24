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
