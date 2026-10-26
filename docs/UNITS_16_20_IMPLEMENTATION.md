# Units 16–20 implementation notes

Status: implementation branch only; not a production launch approval.

## Unit 16 — Organizations and workspaces

Implemented:
- PostgreSQL organization and workspace records with owner/admin/member/viewer roles.
- Organization membership management and workspace membership grants.
- Organization owner/admin inheritance for workspace administration.
- Fail-closed workspace access checks for view, edit, member-management, and admin permissions.
- Owner-protection checks prevent ordinary member-management endpoints from demoting or removing organization/workspace owners; removing an organization member also removes that user's explicit workspace grants in the same transaction.
- Authenticated APIs are mounted under `/api/v1/workspaces`.

Important boundary:
- Existing projects, missions, workflows, artifacts, research, files, and social drafts still use their original owner-scoped service queries. Creating a workspace does not automatically share those existing resources with workspace members. A follow-up migration and resource-by-resource authorization review is required before advertising workspace-wide shared data or collaboration.

## Unit 17 — Sandboxed execution environment

Implemented:
- Authenticated `POST /api/v1/sandbox/python` and owner-scoped run history.
- Execution is disabled by default and fails closed if Docker is unavailable, the feature is disabled, or the image is not both digest-pinned and operator-allowlisted.
- Fixed Python interpreter invocation; no caller-selected image, command, shell, host path, environment, or network access.
- Docker container uses no network, read-only root filesystem, dropped capabilities, no-new-privileges, a non-root UID, PID/memory/CPU limits, a bounded temporary filesystem, a read-only source mount, a 15-second timeout, bounded output capture, full 64-hex SHA-256 digest validation, and best-effort kill plus forced removal on timeout.
- Timed-out containers are explicitly killed. Run metadata and bounded output are recorded.

Required before enabling:
- Build and review a minimal trusted Python image, pin it by digest, add the exact image reference to `SMART_BETHG_DOCKER_ALLOWED_IMAGES`, set `SMART_BETHG_SANDBOX_PYTHON_IMAGE` to that exact reference, and set `SMART_BETHG_SANDBOX_ENABLED=true`.
- Run adversarial tests against the exact production Docker daemon/runtime. The Docker daemon and host kernel remain part of the trust boundary; use rootless Docker or a dedicated isolated runner host where possible.
- This is not a general shell, filesystem, browser, or network automation API.

## Unit 18 — Social content creation and publishing

Implemented:
- Owner-scoped scheduling for approved social drafts, ISO-8601 timezone validation, idempotency keys, list/cancel operations, and a worker-side due-schedule processor.
- Publishing adapter registry is explicit. A due schedule is marked blocked if no real adapter is configured; ambiguous provider outcomes are blocked instead of retried blindly to avoid duplicate posts.
- Successful injected adapters can persist external post identifiers and publication timestamps.

Not implemented:
- No real Facebook, Instagram, LinkedIn, YouTube, X, or blog publishing adapter is registered by this change. Do not claim automatic external publishing is available until each platform's OAuth scopes, token lifecycle, terms, sandbox tests, idempotency behavior, and real account posting have been validated.

## Unit 19 — Monitoring, tracing, and operational observability

Implemented:
- Server-generated `X-Request-ID` response header and correlation ID in request logs.
- Low-cardinality request traces record route templates, method, status, duration, and timestamp. Request bodies, cookies, query strings, and raw path IDs are not recorded.
- Trace retention cleanup removes rows older than 30 days when the worker maintenance cycle runs.
- Separate worker process writes persistent heartbeats every 15 seconds.
- Health check reports worker liveness from database heartbeats.
- Admin-only `GET /api/v1/ops/metrics?hours=24` reports request totals, 4xx/5xx counts, average and p95 duration, top route aggregates, and live worker heartbeats.

Limits:
- These are operational metrics, not a full distributed tracing system, alerting service, external log sink, or SLA dashboard. Configure host/database alerts and protect metrics access in the deployment.

## Unit 20 — Production security, recovery, and launch gates

Implemented:
- Admin-only `GET /api/v1/ops/readiness` checks PostgreSQL connectivity, applied migrations, live worker heartbeat, persistent session-secret status, secure session-cookie configuration, backup/restore drill attestation, and sandbox image configuration when enabled.
- Corrected ephemeral session-secret detection so development's generated process-local key is not misreported as persistent.
- Security middleware adds request correlation while preserving CSRF enforcement, restrictive response headers, configured CORS, and existing session checks.
- Production launch checklist covers backup/restore, schema-upgrade rehearsal, secrets, sandbox configuration, external adapter verification, and privacy/security review.

Important:
- Readiness is a gate, not proof of a backup or legal/security review. `SMART_BETHG_BACKUP_RESTORE_VERIFIED=true` is an operator attestation and must only be set after a successful, documented restore drill.
- Existing CSP is report-only pending compatibility evidence. This branch does not claim a completed penetration test, enforced CSP rollout, multi-region disaster recovery, or legal approval.
- Production readiness should remain not-ready until the worker is live, a backup restore has been tested, and the operator has configured stable secrets and HTTPS cookies.

## New API summary

- `POST/GET /api/v1/workspaces/organizations`
- `GET/POST /api/v1/workspaces/organizations/{organization_id}/members`
- `GET/POST /api/v1/workspaces`
- `POST /api/v1/workspaces/{workspace_id}/members`
- `POST /api/v1/workspaces/{workspace_id}/access-check`
- `POST /api/v1/sandbox/python`, `GET /api/v1/sandbox/runs`
- `POST /api/v1/social-publishing/content/{content_id}/schedule`
- `GET /api/v1/social-publishing/schedules`, `DELETE /api/v1/social-publishing/schedules/{schedule_id}`
- `GET /api/v1/ops/metrics`, `GET /api/v1/ops/readiness` (admin-only)

Run the worker separately with `python scripts/run_worker.py`. Do not merge or deploy this branch until the latest CI passes and the explicit remaining boundaries above are accepted.
