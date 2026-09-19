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

V1 should maintain persistent local storage.

Required capability:
- SQLite support for the current V1.
- Database configuration through `DATABASE_URL`.
- A clear boundary preventing non-SQLite URLs from being passed to `sqlite3.connect()`.
- Automatic creation of required storage directories.
- Persistent database tables for V1 systems.
- Transaction commit/rollback handling.
- Safe connection cleanup.

`DATABASE_URL` is retained now as a configuration boundary for future database-engine migration. It does not mean PostgreSQL/MySQL support is already implemented.

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
| Storage/database foundation | IMPLEMENTED | `DATABASE_URL` boundary enforced (sqlite only, fails fast otherwise). Storage directories auto-created via `config.ensure_storage_dirs()`. |
| UI/UX direction | PARTIALLY IMPLEMENTED | Chat and home dashboard are real, responsive, and reachable. Study/Developer/Social/Automation are intentionally unlinked because their templates are empty - see Section 18 rule against exposing categories with no capability behind them. |
