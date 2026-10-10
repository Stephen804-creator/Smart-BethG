# Smart BethG Architecture and Decisions

Last reviewed: 2026-10-10. This records current decisions; deferred capabilities are not represented as implemented.

## Product boundary
Until the owner explicitly chooses a public launch, operate Smart BethG as a personal / small trusted-group application. Do not invite strangers or advertise public registration before the security review, consent flow, privacy policy, and operational safeguards are complete. Registration defaults to closed in every environment; an operator must deliberately open it through SMART_BETHG_REGISTRATION_OPEN=true.

## Planning and execution safety
Keep the fixed-shape planner for now. It is auditable and predictable, while a general planner expands the action space and can chain unsafe or unintended operations. Do not add a general autonomous planner until each tool has explicit authorization, risk classification, approval enforcement, audit events, bounded execution, cancellation, and adversarial tests. Multi-step work should remain a small set of reviewed, named plan templates.

## Token budgets
Use per-user budgets as the primary fairness and abuse-control boundary, with a separate global platform spending ceiling as a circuit breaker. Enforce limits server-side and atomically before a provider call. Record provider/model, estimated input and output tokens, actual usage when available, and cost where known. Never rely on frontend-only counters. A global ceiling must stop new paid calls safely without corrupting user sessions or conversation data. Budget implementation is not complete until concurrent-request tests prove limits cannot be overspent.

## Database and deployment
SQLite is acceptable only for the current single-instance personal/small-team deployment. DATABASE_URL is a migration boundary, not PostgreSQL support. Before multi-instance deployment, migrate to PostgreSQL and test migrations, transaction semantics, backups, restore, and connection handling. Do not run multiple application instances with SQLite as shared mutable state.

The storage root must point to a persistent mounted disk in the hosting provider. Database, uploads, and user-created artifacts must survive redeploys. Backups must be independent of that disk and periodically restore-tested. The deployment configuration has not been independently verified by this document.

### Live deployment verification checklist
Do not mark persistence as verified until these steps have been completed against the actual hosted service:
1. In the host dashboard, confirm a persistent disk is attached and record its mount path.
2. Set SMART_BETHG_STORAGE_ROOT to that exact mount path (for example, /var/data/smartbethg only if that is the configured mount path). Confirm the database resolves below this root; do not set a conflicting SMART_BETHG_DB path.
3. Set SMART_BETHG_ENV=production, a long random SMART_BETHG_SECRET_KEY, SMART_BETHG_SESSION_HTTPS_ONLY=true, and SMART_BETHG_REGISTRATION_OPEN=false. Set SMART_BETHG_ALLOWED_ORIGINS only to the actual trusted frontend origins.
4. Create a non-sensitive test record while signed in, deploy/restart the service, then confirm the record and login still work. Repeat after a redeploy, not only a process restart.
5. Configure an independent backup destination and retention policy. Restore a backup into a separate test environment and document the result before storing real user data.
6. Record the date, operator, deployed commit, disk path, backup location, and test outcome. Until this evidence exists, persistent storage and recovery remain unverified.

## Scaling boundaries
The in-process rate limiter and in-Python cosine similarity are single-instance-only. Before horizontal scaling, move rate-limit counters to a shared store and knowledge retrieval to a shared, indexed database/vector-search implementation. Do not assume increasing server size fixes cross-instance correctness.

## Approval workflow boundary
Pending approval records are persisted and scoped to their owner, and the UI can record approve/reject decisions. Recording a decision does not yet resume or execute the interrupted operation. Never treat a recorded approval as authorization to run a tool unless the execution path checks the same approval record immediately before the side effect, validates its owner and action/resource binding, and safely handles expiry, rejection, cancellation, and duplicate execution.

## Schema-only tables
Do not delete tables solely because they are not yet used; removal may break future migrations or existing data. Treat missions, workflows, artifacts, social_content, and projects as deferred schema. Either implement a real vertical slice with tests and UI before marketing those features, or remove them in a deliberate versioned migration after checking all references and data. Keep them unadvertised meanwhile.

## Security and privacy release gates
Before public access:
- Wire and test exact-origin CORS configuration.
- Keep production registration closed unless intentionally enabled.
- Publish reviewed Terms of Service and Privacy Policy.
- Obtain explicit, revocable consent before conversations are eligible for training export; existing conversations are not automatically consented.
- Add HTTP-level authentication, authorization, ownership-isolation, CSRF, and session tests; obtain an independent security review.
- Run dependency vulnerability scanning and secret scanning in CI.
- Document deletion, export, retention, and backup/restore behavior.

## Testing and delivery
CI runs compilation and the existing unit suite, with HTTP boundary and approval-service regression tests being expanded on the review branch. This is a starting gate, not proof of end-to-end correctness. Add browser-flow tests, dependency scans, and deployment smoke tests. A green CI run must not be represented as a penetration test or live-deployment verification.
