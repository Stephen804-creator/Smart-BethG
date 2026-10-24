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
