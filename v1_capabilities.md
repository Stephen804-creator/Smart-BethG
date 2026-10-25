# Smart BethG V1 Capabilities

Version: 002
Status: Current V1 target

This document defines what Smart BethG V1 is intended to be capable of. It does not claim that every listed capability is already implemented.

## 1. Core V1 Principle

Smart BethG V1 must not be an empty application shell.

The V1 target is a usable foundation for an AI-agent system that can receive a user's objective, organize work around it, use available knowledge and tools honestly, execute structured work, preserve useful state, and produce usable outputs.

A capability is IMPLEMENTED only when its functional body exists, has been reviewed, and works as intended.

A route, database table, folder, interface, placeholder, or architectural boundary alone does not count as implementation.

## 2. Mission-Centered Operation

V1 should support missions as first-class work units.

Required capability:
- Accept a user's objective as a mission.
- Track mission status and priority.
- Record creation and update times.
- Separate a mission from individual execution attempts.
- Track execution status, completion, and errors.
- Preserve mission history.

The database therefore contains `missions` and `mission_runs`.

## 3. Knowledge Gateway

V1 should have a Knowledge Gateway as the public entry point for obtaining knowledge.

The gateway must distinguish source selection from actual collection.

Current architectural truth:
- The gateway may determine which knowledge source/capability should be used.
- It must not pretend that a real web browser, internet search, CAD system, external AI, or other connector exists when it has not been implemented.
- `search()` may serve as the public entry point and internally call `collect()` while connector implementations are being developed.
- Real connectors should be added behind the gateway rather than scattered through mission code.

A gateway existing does not mean real internet or external-source collection exists.

## 4. Local and User-Provided Knowledge

V1 should work with knowledge supplied locally by the user.

Required capability:
- Accept uploaded files.
- Track file metadata, location, type, source, and status.
- Provide storage for memory, research, projects, and other V1 data.
- Allow knowledge-processing components to use stored material.

The `files` table records information about files; physical files remain in their storage directories.

## 5. Memory

V1 should provide persistent memory storage.

Required capability:
- Store memory records.
- Give entries identifiers.
- Store titles and content.
- Record creation time.
- Provide a foundation for future memory retrieval and organization.

The memory table alone does not mean intelligent memory retrieval is implemented.

## 6. Research and Evidence

V1 should provide a foundation for research-oriented work.

Required capability:
- Store research topics, summaries, and source information.
- Store mission-associated evidence.
- Preserve claims and supporting evidence.
- Track validation status.

Research storage does not mean real web research is implemented. Real external research requires an actual connector.

## 7. Agent Execution Foundation

V1 should move beyond a simple question-and-answer interface toward structured agent execution.

Required direction:
- Receive a mission.
- Organize execution.
- Track execution runs.
- Record important execution events.
- Allow multiple attempts for one mission.
- Capture errors.
- Produce outputs as artifacts.

Controllers, execution services, plugins, and specialized systems may be used where their responsibilities are distinct. They should not be forced into `KnowledgeGateway.py` when the responsibility belongs elsewhere.

## 8. Workflows

V1 should have a workflow foundation for repeatable processes.

Required capability:
- Store workflow definitions.
- Give workflows names and descriptions.
- Track workflow status.
- Preserve creation/update times.
- Provide a foundation for future workflow execution and orchestration.

A workflow table or folder does not by itself mean workflow execution is complete.

## 9. Artifacts

V1 should treat generated and useful outputs as first-class artifacts.

Required capability:
- Record artifacts produced by missions.
- Associate artifacts with missions where applicable.
- Store artifact name, type, path, and status.
- Provide physical artifact storage.
- Support future generated documents, reports, images, spreadsheets, technical drawings, and other usable outputs.

An artifact table does not equal an artifact-generation engine.

## 10. Evidence and Validation

Where Smart BethG produces research-based or mission-based conclusions, V1 should preserve supporting evidence.

Required direction:
- Record source/reference information.
- Associate evidence with missions where applicable.
- Preserve the claim being supported.
- Preserve the evidence itself.
- Track validation status.

Smart BethG must not claim information is verified when no actual validation has occurred.

## 11. Logging and Operational History

V1 should maintain runtime logs.

Required capability:
- Record important application events.
- Record event level, type, message, and timestamp.
- Associate logs with missions where appropriate.

Important distinction:

`logs` = events that happen while Smart BethG runs.

`changelog.md` = changes made to the Smart BethG software.

They must remain separate.

## 12. Authentication Foundation

V1 should have a real authentication capability rather than merely displaying login/logout pages.

Required direction:
- Provide a login interface.
- Accept login submissions.
- Authenticate users through a dedicated authentication service.
- Store users through an appropriate persistent user-data layer.
- Never hard-code real credentials in source code.
- Store passwords securely using password hashing.
- Establish authenticated session state after successful authentication.
- Clear authentication state during logout.
- Provide authentication feedback.
- Protect routes that require authentication.
- Configure Flask session security appropriately.
- Keep authentication routes separate from authentication/business logic.

Current distinction:
- `/login` route structure exists.
- `/logout` can clear the Flask session.
- Real credential verification is not complete merely because these routes exist.
- A hard-coded `admin/password` check is not an acceptable final V1 authentication implementation.

Intended architecture:

`auth routes -> authentication service -> user/data layer -> session state`

This prevents `auth.py` from becoming a monolithic authentication module.

## 13. Web Application Foundation

V1 should provide a usable Flask application foundation.

Required capability:
- Flask application entry point.
- Configuration separation.
- Blueprint-based route organization.
- Template rendering.
- Environment-based server configuration.
- Clear separation between application startup and feature modules.
- A structure that can move from development toward production deployment.

## 14. Storage and Database Foundation

V1 must use PostgreSQL as its single application database in local development, tests, and production.

Required capability:
- PostgreSQL connection configuration through `DATABASE_URL` in every environment.
- No SQLite runtime fallback or second schema-initialization path.
- Automatic creation of required storage directories.
- Persistent database tables for V1 systems, created through ordered PostgreSQL migrations.
- Transaction commit/rollback handling.
- Safe connection cleanup.
- A separate, explicit one-way utility to import legacy SQLite data into a fresh PostgreSQL database without modifying the source.

PostgreSQL support is implemented in the application code, but the PostgreSQL-only refactor on branch `feat/postgresql-only-2026-10-13` still requires CI and migration-rehearsal verification before merge.

## 15. V1 Storage Areas

The current configuration defines physical storage locations for:

- uploads
- memory
- research
- projects
- social content
- missions
- artifacts
- workflows
- logs

These directories are created when required by storage/database initialization.

A directory existing does not mean its intelligent capability is complete.

## 16. Social Content Foundation

V1 should have a foundation for social-media content management.

Required capability:
- Store platform, topic/title, captions, hashtags, and status.
- Preserve creation time.
- Provide storage for associated social content.

Actual platform publishing/integration must not be claimed unless a real connector exists.

## 17. Project Management Foundation

V1 should maintain project-level information for longer-running work.

Required capability:
- Project name.
- Project description.
- Project status.
- Project creation time.
- Persistent project storage.

Projects may later contain missions, research, files, workflows, and artifacts.

## 18. UI/UX Direction

V1 must not merely expose technically functional routes with a poor or empty interface.

The interface should progressively provide:
- Clear navigation.
- Consistent visual structure.
- Useful empty states.
- Loading/progress states for long operations.
- Understandable error states.
- Clear mission/work status.
- Usable artifact presentation.
- A coherent visual language.

UI quality is part of the product, not merely decoration.

UI polish must still be distinguished from backend capability.

## 19. Honest Capability Boundaries

Smart BethG must never claim a capability merely because a file, table, route, folder, interface, or placeholder exists.

Examples:

A Knowledge Gateway does not equal real web search.

A login page does not equal authentication.

An artifact table does not equal generation.

A workflow table does not equal workflow execution.

A research table does not equal internet research.

A memory table does not equal intelligent memory.

A connector interface does not equal a working connector.

This principle is mandatory for V1.

## 20. Future-Ready Architecture

V1 should allow future capabilities to be added without rewriting unrelated systems.

Examples include:
- Real web/browser connectors.
- External AI connectors.
- CAD/technical-tool connectors.
- Additional knowledge sources.
- Stronger workflow execution.
- Advanced artifact generation.
- Richer memory retrieval.
- Production database engines.
- Mobile/full-size generation interfaces.
- Additional agent tools and plugins.

These become implemented capabilities only when their functional bodies are built and reviewed.

## 21. Implementation Tracking Rule

During every code review, compare the file against this V1 capability document.

Ask:
1. Does this file implement part of an existing V1 capability?
2. Is a required V1 capability missing from this file?
3. Has an earlier architectural decision introduced a requirement this file must support?
4. Is the code pretending to provide something that is only a placeholder?
5. Does the implementation create a new capability that should be recorded?
6. Does the capability belong in another module?
7. Is an existing capability actually functional or merely structurally prepared?

This prevents old files from being accepted simply because their original code was once considered good enough.

## 22. Status Vocabulary

IMPLEMENTED:
The functional capability exists and has been reviewed.

PARTIALLY IMPLEMENTED:
Some functional parts exist, but the complete capability is unavailable.

STRUCTURALLY PREPARED:
The architecture/code provides a place for the capability, but its functional body is not implemented.

PLANNED:
The capability is approved for a future version but is not part of the current implementation target.

IDEA:
A possibility that has not been approved as a committed capability.

NOT IMPLEMENTED:
The capability is required by the current target but has not yet been built.

## 23. Relationship With Other Project Documents

`idea.md`
Contains uncommitted ideas and possibilities.

`roadmap.md`
Contains approved future capabilities and version targets.

`Smart BethG V1 Capabilities.md`
Defines the current V1 target and is the primary reference during code review.

`changelog.md`
Records what has actually changed in the software, with timestamps and entry/version numbering.

A proposal should not automatically become a V1 capability.

A V1 capability should not automatically be described as implemented.

An implemented change should be recorded in the changelog.

## 24. Review Rule Going Forward

Whenever a project file is submitted for review, its code must be evaluated against this document before being declared acceptable.

If the file is technically valid but fails to support a required V1 capability, it must be revised or its responsibility must be explicitly assigned to another module.

If a new capability is discovered during review:
- determine whether it is required for V1;
- determine which file/module owns it;
- update this document if it becomes a V1 requirement;
- otherwise place it in the appropriate roadmap or ideas document.

This document is the living definition of the current Smart BethG V1 target.

## 25. Current Implementation Status (Review: 2026-09-19)

This section is maintained by comparing the actual codebase against the
sections above, per the Implementation Tracking Rule (Section 21). It
will drift from reality again as soon as new code lands without a
matching review - treat it as a snapshot, not a guarantee.

| Area | Status | Notes |
|---|---|---|
| Web application foundation | IMPLEMENTED | FastAPI app now serves the actual UI: static assets mounted, templates render, session middleware configured. Previously STRUCTURALLY PREPARED only - templates and CSS existed but nothing served them. |
| Authentication | PARTIALLY IMPLEMENTED | Real password hashing, real session cookies signed with SECRET_KEY, login/logout/register all functional. Registration is intentionally open for pre-launch testing (see routes/auth.py docstring) and must be locked down before a public domain goes live. No password reset, no rate limiting, no email verification. |
| Chat / conversational assistance | PARTIALLY IMPLEMENTED | Real endpoint, real persistence, real Anthropic/OpenAI/Google providers (each active when its API key is set), per-message provider selection in the UI. Honestly reports "not configured" when no provider is available. No streaming yet; provider choice is per-message, not a saved per-user preference. |
| Mission-centered operation | STRUCTURALLY PREPARED | `missions` / `mission_runs` tables now exist. No mission creation UI, no execution loop reads or writes them yet. |
| Knowledge Gateway | STRUCTURALLY PREPARED | `KnowledgeGateway.retrieve()` still returns `[]`. No connector exists. |
| Memory | STRUCTURALLY PREPARED | `memory` table now exists. `memory.py`'s `Memory` class is still in-process only (lost on restart) and unconnected to the table or to chat. |
| Research & evidence | STRUCTURALLY PREPARED | `research` / `evidence` tables now exist. No research connector, no writer. |
| Agent execution foundation | STRUCTURALLY PREPARED | `POST /tasks` still only inserts a `queued` row. `ExecutionEngine`/`ToolOrchestrator`/security stack is real but nothing invokes it automatically yet. |
| Workflows | STRUCTURALLY PREPARED | `workflows` table now exists. No execution. |
| Artifacts | STRUCTURALLY PREPARED | `artifacts` table now exists. No generation engine. |
| Files | STRUCTURALLY PREPARED | `files` table now exists. No upload endpoint yet. |
| Social content | STRUCTURALLY PREPARED | `social_content` table now exists. No connector, no writer. |
| Projects | STRUCTURALLY PREPARED | `projects` table now exists. No CRUD yet. |
| Logging | STRUCTURALLY PREPARED | `logs` table now exists. Nothing writes to it yet (audit_events is separate and does have a writer). |
| Storage/database foundation | IMPLEMENTED (PostgreSQL-only runtime; verification pending on this branch) | `DATABASE_URL` must point to PostgreSQL in every environment; no SQLite runtime fallback. Storage directories auto-created via `config.ensure_storage_dirs()`. Legacy SQLite import remains a separate one-way migration tool. |
| Testing | IMPLEMENTED (foundation only) | 42 real unit tests in `tests/`, run via `python -m unittest discover -s tests`. Covers service/logic layer. No integration or end-to-end tests against a running server yet (still can't run the actual FastAPI app in the environment this was built in). |
| Logging | IMPLEMENTED | Structured logging to stdout + best-effort rotating files. Named loggers per subsystem. Request logging middleware logs every request's method/path/status/duration. |
| Error handling | IMPLEMENTED | Centralized handlers for HTTP exceptions, validation errors, and unexpected exceptions. Consistent `{"error": {...}}` response shape. Tracebacks logged server-side only. |
| API versioning | IMPLEMENTED | `/api/v1` canonical prefix, old unversioned paths kept working (dual-mounted, same handlers). Google OAuth intentionally excluded from dual-mounting. |
| Health checks | IMPLEMENTED | `/health` performs real DB and provider checks. Background worker honestly reported `not_implemented`. |
| Authorization/roles | IMPLEMENTED (coarse) | `users.role` (`user`/`admin`) mapped to real tool permissions via `security/role_permissions.py`. Only two roles exist; no per-permission grants yet. |
| Approval workflow | IMPLEMENTED | Was broken (in-memory, wiped every request) - now persists to the `approvals` table and is actually reachable end-to-end: a high-risk tool call creates a real pending approval. |
| Agent architecture (request model, intent detection, planning, execution loop, result verifier) | PARTIALLY IMPLEMENTED | Real end-to-end loop exists (`agent/` package, wired into `Controller`). Intent detection recognizes exactly one tool trigger (`git.read`); everything else still falls through to chat. Planning is single-step only by design - no multi-step decomposition. |
| Tool registry/execution engine | IMPLEMENTED (all 7 tools) | `filesystem.read/write`, `git.read/write`, `terminal.execute`, `network.request`, `docker.run` all wired through the real permission/risk/approval/verification pipeline. |
| Training data export (admin-only) | IMPLEMENTED | `GET /admin/training-export`, gated by `require_role("admin")`. Real AI-provider exchanges only (excludes failure messages and synthesized tool/memory replies), no user identity included. Not wired to any training/retraining loop - feeds an offline, operator-controlled fine-tuning process. |
| Free/open-weight providers (Groq, OpenRouter) | IMPLEMENTED | Both register automatically as real fallback-order candidates; become the default with zero configuration when no paid provider key exists. Model catalog uses verified current IDs (Groq retires models on a published schedule; OpenRouter's free lineup via `openrouter/free`, their own always-current auto-router). |
| Provider fallback | IMPLEMENTED | If the selected/auto-chosen provider fails, chat automatically tries every other configured provider before giving up. |
| Model evaluation | IMPLEMENTED | Every provider call attempt (success or failure, including ones hidden behind a fallback) is recorded with latency. `GET /api/chat/model-stats`. |
| Audit trail | IMPLEMENTED | Previously nothing wrote to `audit_events` despite the table/route existing - every tool authorization decision is now recorded. `GET /audit/all` is a real admin-only endpoint. |
| Chat ↔ agent loop | IMPLEMENTED (multi-step for research) | `POST /api/chat` routes through the agent loop. Recognized intents: `git.read`, `memory.write`, `filesystem.read` (asks rather than guesses when the path is unclear), `research` (genuine 2-step: search then grounded synthesis). Everything else falls through to chat. |
| Multi-step planning | IMPLEMENTED (fixed shapes only) | The executor runs every step of a plan in order, carrying context forward - not just the first step. Only hand-written plan shapes exist (single-step for most intents, a fixed 2-step search→synthesize shape for research); there is no general planner that can construct an arbitrary step sequence. |
| Knowledge base / RAG (T0901-T0904) | IMPLEMENTED (semantic only with an OpenAI/Google key) | Explicit ingest of uploaded files into chunks; cosine-similarity retrieval over embeddings when an embedding-capable provider is configured, honest keyword-overlap fallback otherwise. Injected into chat automatically for users who have ingested files. No vector DB - in-Python similarity, fine for personal scale only. |
| Code intelligence (T1101, T1104, T1105) | IMPLEMENTED | `code.explain` / `code.review` = real permission-checked file read + AI step that receives the actual contents. Stops honestly if the read fails. |
| Code generation / modification (T1102, T1103) | NOT A DEDICATED FEATURE | Generation works via plain chat. Auto-applying AI-written code to files from chat text is deliberately not built (a wrong extraction overwrites a real file). `filesystem.write` exists, approval-gated, for explicit structured calls. |
| Native packaging | PARTIAL - PWA works, native shell configured but unbuilt | Installable PWA works today. `native/` holds a Capacitor shell that loads the deployed URL (env-driven, https only); never built or run by me; Apple may reject webview wrappers. No desktop wrapper. |
| Web research (T1001-T1004) | IMPLEMENTED | Real search via Brave Search API (`BRAVE_SEARCH_API_KEY`). Answers are grounded in actual search results with required citations; honestly fails if search is unconfigured or returns nothing, rather than letting the AI fabricate an answer. Single-query only - no multi-query decomposition of a broad topic. Verification is prompt-level, not a separate fact-checking pass. |
| File management | IMPLEMENTED | Real upload/list/download/delete/search against the `files` table. Text extraction for plain-text files and PDFs (via `pypdf`); AI summarization when a provider is configured. |
| Memory (working/session/user/project/retrieval/governance) | IMPLEMENTED (non-embedding retrieval) | Three scopes: conversation (collapses working+session), user, project. Retrieval returns everything in scope (capped), not semantic search - documented as not scaling past a handful of entries per user. Governance is real: list/delete/delete-all via `/api/memory`. Actually injected into every chat request, not just stored. |
| UI/UX direction | PARTIALLY IMPLEMENTED | Chat and home dashboard are real, responsive, and reachable. Study/Developer/Social/Automation are intentionally unlinked because their templates are empty - see Section 18 rule against exposing categories with no capability behind them. |

## 26. Review update — 2026-10-24 (Units 2–4)

This dated review supersedes earlier status-table notes for the storage, memory,
and uploaded-knowledge areas above. It records the current branch state and
does not imply that PR #12 has merged.

| Area | Current status | Boundaries |
|---|---|---|
| Upload and artifact storage | PARTIALLY IMPLEMENTED | Both use owner-scoped local/S3-compatible adapters. A dry-run-first migration utility now migrates database-referenced uploads/artifacts, verifies copied bytes with SHA-256, checks concurrent row changes, and retains source files. |
| Multi-instance storage | NOT COMPLETE | Other live filesystem-backed workspace/research/social/mission/workflow paths still need inventory and migration. Cross-instance tests, backup/restore, orphan cleanup, and production migration rehearsal remain required. |
| Memory metadata and context | IMPLEMENTED FOUNDATION | Typed memory, confidence, provenance, metadata, expiry, scope isolation, and bounded context assembly are implemented in the current PR branch. |
| Memory conflict handling | PARTIALLY IMPLEMENTED | Conservative polarity/numeric disagreement signals flag potential conflicts and preserve both entries. They do not determine which memory is correct. |
| Semantic memory retrieval | PLANNED | Provider-backed embedding retrieval with budget controls and model-versioning is not implemented yet. |
| Knowledge retrieval | IMPLEMENTED FOUNDATION | Chunking, atomic reindexing, optional embedding search with keyword fallback, relevance metadata, and source citations exist. |
| Knowledge disagreement handling | PARTIALLY IMPLEMENTED | Conservative signals flag possible polarity/numeric differences between retrieved excerpts; this is not independent source verification. |
| OCR, advanced reranking, external verification | PLANNED | These remain roadmap items and must not be described as implemented. |
| Verification | PENDING | The current PR must pass the latest unit tests, PostgreSQL integration tests, dependency audit, and secret scan before merge. |

See docs/UNITS_2_4_REMAINING_WORK.md and roadmap.md for explicit completion gates.


## 27. Review update — 2026-10-24 (Units 5–9)

This review supersedes earlier status-table claims above for connector execution,
missions, and background jobs. It describes the current feature branch only;
PR #13 is not merged, and the latest connector changes still require a fresh CI run.

| Area | Current status | Boundaries |
|---|---|---|
| Typed connector capabilities | IMPLEMENTED FOUNDATION | Trusted code-defined action schemas, type/required-field checks, risk labels, and app-level permission identifiers. No public third-party SDK or remote manifest versioning. |
| External connector platform | IMPLEMENTED FOUNDATION | Owner-scoped installations, permission grants, OAuth flows for GitHub/Google Drive/Slack, Google PKCE, encrypted per-installation credentials, and trusted provider adapters exist. OAuth app credentials must be configured by the deployment operator. |
| Live provider actions | IMPLEMENTED FOUNDATION | GitHub issue list/create, Google Drive file search, and Slack message send are implemented. Real account access has not been verified against provider sandbox accounts in this branch. |
| Connector credential lifecycle | PARTIALLY IMPLEMENTED | Tokens are Fernet-encrypted in PostgreSQL using a stable deployment secret; Google refresh and provider revocation where supported are implemented. Operator-managed KMS/secret-manager integration and key-rotation migration remain open. |
| Connector policy and approvals | IMPLEMENTED FOUNDATION | Owner, connection, capability, and app-permission checks fail closed. Side-effecting actions require durable approval and are revalidated before execution. Legacy host-side actions remain disabled. |
| Durable jobs | IMPLEMENTED FOUNDATION | PostgreSQL-backed queue, idempotency keys, priorities, leases, heartbeat, bounded retry/backoff, stale-lease cleanup, owner-scoped status/cancellation, and separate worker entry point. At-least-once delivery is not exactly-once execution. |
| Mission execution | IMPLEMENTED FOUNDATION | Bounded connector-action plans execute in order, persist progress, and pause/resume around approval. Natural-language plan generation and saga/compensation recovery are not implemented. |
| Reliability verification | PENDING | New connector tests have been added, but fresh CI is still required. Multi-worker crash/replay, full OAuth callback, live provider sandbox, and end-to-end approval/resume tests remain release gates. |

See docs/UNITS_6_9_IMPLEMENTATION.md and roadmap.md for configuration and release
requirements. Do not describe these foundations as a production-verified or
fully multi-instance deployment.


## Units 10–15 status addendum (2026-10-24)

The feature branch contains initial foundations, not production-complete roadmap implementations:
- Validated workflows can be queued and tracked. The current worker dispatches mission steps only; workflow run completion means all child missions were dispatched, not that those missions finished.
- Specialist coordination persists role assignments but does not execute independent specialist models.
- Decision records and deterministic evaluation scores are owner-scoped. Scores are signals, not factual verification.
- Model routing is a preview only; it does not call a provider or reserve/reconcile usage budgets.
- Account data export and lifecycle requests exist. Deletion is not automatically performed and account-recovery delivery is not wired.


## Units 10–15 follow-up status — 2026-10-25

This section describes the PR #17 follow-up branch; it is not a production launch approval.

| Area | Current status | Boundaries |
|---|---|---|
| Workflow execution | IMPLEMENTED FOUNDATION | Durable step ledger, sequential mission/research-record/artifact/social-draft steps, bounded condition operators, downstream step skipping, completion aggregation, and guarded step replay. Ambiguous side-effect replays fail closed; compensation and external publishing are not implemented. |
| Specialist coordination | IMPLEMENTED FOUNDATION | Role-specific calls use configured ChatService providers and existing usage budgets; results are persisted and later roles receive earlier contributions as context. Specialists do not execute tools and are not independently routed to distinct models. |
| Decision ledger | PARTIALLY IMPLEMENTED | Workflow completion and specialist result decisions are recorded with evidence references. Complete decision instrumentation and enforced immutable retention are not implemented. |
| Evaluation | PARTIALLY IMPLEMENTED | Deterministic rubric, human labels, and Brier/MAE diagnostics exist. Fewer than 10 labels are reported as insufficient; there is no reviewed benchmark corpus or independent factuality guarantee. |
| Cost-aware routing | IMPLEMENTED FOUNDATION | Auto chat selection uses the cost-aware route preview, then existing ChatService budget reservation/reconciliation and provider telemetry. Live catalog smoke tests and latency/reliability-informed optimization remain open. |
| Data export | IMPLEMENTED FOUNDATION | Owner-scoped export manifest, reviewed parent scoping for mission runs/messages, recursive sensitive-key filtering, limits, and explicit omissions/truncation reporting. Export completeness depends on the manifest; omitted tables must not be assumed included. |
| Account recovery/deletion | PARTIALLY IMPLEMENTED | Lifecycle requests are persisted. Verified recovery delivery, identity confirmation, automated deletion, retention enforcement, and legal/privacy approval are not wired. |
| Verification | PENDING | Review the latest PR #17 workflow runs. No live provider sandbox, production recovery/deletion, or multi-worker crash/replay verification is claimed. |
