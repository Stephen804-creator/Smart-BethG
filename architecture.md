# Smart BethG Architecture and Decisions

**Status:** Active engineering decisions  
**Last updated:** 2026-10-10 20:10 UTC  
**Decision history:** See `docs/DECISION_LOG.md`; the Git commit timestamp is the precise change record.

## Product goal and release posture

Smart BethG is being built for a public launch, not only for personal use or a small trusted group. Public launch is the target architecture; it is not yet a claim that the current application is safe or ready for unrestricted public access. Registration remains closed by default until the release gates in this document are met.

## Database: PostgreSQL is the production standard

PostgreSQL is the only application database in local development, tests, and production, whether deployment has one application instance or several. The application has no SQLite runtime adapter or fallback. A legacy SQLite file may be read only by the explicit one-way migration utility. Startup fails closed if DATABASE_URL does not point to PostgreSQL.

PostgreSQL schema initialization now uses a numbered migration directory (`migrations/postgresql/`) and records applied versions in `schema_migrations`. The first idempotent baseline migration can also adopt a database initialized by the earlier compatibility adapter. The SQL compatibility adapter remains in place for repository queries, so this is the start of a versioned migration system—not proof that every query or upgrade path is production-verified. Every future schema change must be a new numbered migration; never silently rewrite an already-released migration. PostgreSQL integration CI must pass before merging or deploying. Any SQL behavior that differs between SQLite and PostgreSQL must be covered by regression tests.

A migration utility and a tested backup/restore procedure are required before moving real user data. Do not point a new deployment at a database containing important data until a backup has been taken and the migration has been tested on a copy.

## Single-instance and multi-instance operation

Local development and deployment use the same database engine: PostgreSQL. One or multiple application instances use shared PostgreSQL, server-side authorization, and shared rate-limit records.

The database-backed authentication limiter uses PostgreSQL transaction-scoped advisory locks and shared rows to serialize attempts across processes. Future high-volume traffic may justify a dedicated shared rate-limit service, but a per-process in-memory counter must not be used in production.

**Multi-instance limitation still requiring an explicit implementation:** local filesystem paths are not shared across app replicas. Before enabling multiple instances, file uploads, generated artifacts, and any workspace data that must be visible on every replica need a shared object-storage adapter or shared storage service. Do not assume PostgreSQL alone makes local files multi-instance safe. Provider calls and background work also need bounded concurrency, durable job state, cancellation semantics, and idempotency before worker replicas are scaled.

## Planning and execution safety

Keep the fixed-shape planner until tool authorization, action/resource binding, durable approvals, cancellation, bounded execution, audit events, and adversarial tests are enforced end to end. General autonomous planning is not a prerequisite for launch and must not bypass the security policy.

## Approval workflow

An approval must refer to one authenticated owner, one exact action, one exact resource/workspace, and a bounded set of arguments. On approval, the application should resume that saved operation once, after re-checking current permissions and validating the action/resource binding. It must reject changed payloads, expired approvals, rejected requests, and duplicate execution attempts.

A decision record by itself is not execution. The current review branch now has a route that resumes the exact saved operation after approval, rechecks authorization, claims execution atomically, records the outcome, and refuses duplicate execution. The route test verifies a Git operation executes once; a recovery test also covers the narrow case where the decision was committed before execution was claimed. That new recovery test must pass the latest CI run before merge. If the process crashes after the operation is claimed or during an external side effect, the record must not be blindly replayed; it requires an explicit reconciliation path because the outcome may be indeterminate.

## Token budgets and spending

Use per-user budgets for fairness and abuse prevention plus a global spending ceiling as a platform circuit breaker. Limits must be enforced server-side and atomically before paid provider calls. Record provider/model, input/output token usage where available, and cost where known. Concurrent-request tests must demonstrate that limits cannot be overspent. Do not treat frontend counters as enforcement.

## Capability areas must become real features

The following tables are deliberate product foundations, not features to leave unused indefinitely: missions and mission runs, workflows, artifacts, social content, projects, research, evidence, files, memory, and logs. Build them as vertical slices, each with authenticated APIs, owner-scoped queries, validation, UI, audit events where appropriate, and tests. A table alone does not count as an implemented capability.

Implementation order should favor the shared foundation first: projects/workspaces and files/artifacts; mission lifecycle and runs; reusable workflows; research/evidence attached to missions; social-content drafts and publishing lifecycle. Do not expose a feature as available in the product until its complete vertical slice works. Do not remove schema merely because the first implementation is incomplete; use versioned migrations after checking references and data.

## Storage and portability

The application must not depend on Render-specific configuration, services, or deployment manifests. It should run locally and be deployable to any compatible Linux/Python host using documented environment variables and a standard ASGI entry point. Render may be used as a low-cost test target, but it is only one deployment option. Keep host-specific setup outside the application core.

Local filesystem storage is for development and single-instance testing. Production must explicitly configure durable storage; multi-instance operation requires shared object storage or an equivalent shared service. Backups must be independent of primary storage and periodically restore-tested.

## Security, privacy, and public-launch gates

Before unrestricted public registration:
- Complete authentication, session, CSRF, ownership-isolation, and authorization tests across every API route.
- Keep registration closed by default and add abuse controls for registration, login, provider calls, uploads, and tool execution.
- Publish reviewed Terms of Service and Privacy Policy; draft documents are tracked separately and are not legal approval.
- Obtain explicit, informed, recorded, revocable consent before a user's conversation is eligible for training export. Admin permission is not user consent.
- Run dependency and secret scanning in CI; remediate high/critical findings or document a time-bounded exception.
- Verify rate limiting across multiple app instances against shared PostgreSQL.
- Verify backups and restoration, durable file storage, deployment rollback, and health checks.
- Obtain an independent security review and run end-to-end browser tests, including unauthorized cross-user access attempts.

## CI and verification truth

The CI suite must run the unit tests and PostgreSQL integration tests. A green run is evidence only for the tests that actually ran; it is not a penetration test, legal review, load test, or live deployment verification. Every significant decision and fix should be timestamped in the decision log/changelog, with the exact Git commit serving as the source of truth.
