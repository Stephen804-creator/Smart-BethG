# Smart BethG Production Launch Checklist — 2026-10-26

This checklist is an operational gate, not a statement of compliance. Keep the service private until all applicable items are evidenced.

## Deployment and secrets

- [ ] Set `SMART_BETHG_ENV=production`.
- [ ] Set a stable random `SMART_BETHG_SECRET_KEY` (at least 32 characters) in the hosting secret manager; verify every replica uses the same value.
- [ ] Set `SMART_BETHG_SESSION_HTTPS_ONLY=true` and terminate HTTPS correctly at the trusted proxy.
- [ ] Set a TLS-enabled PostgreSQL `DATABASE_URL`; restrict database network access to app/worker hosts.
- [ ] Run `python scripts/run_worker.py` as a separate supervised process; verify its heartbeat appears in `/api/v1/ops/metrics`.
- [ ] Confirm logs and telemetry do not include authorization headers, cookies, request bodies, prompts, or provider secrets.

## Database and recovery

- [ ] Take a verified database backup before schema changes.
- [ ] Rehearse every unapplied migration against a restored copy of the target schema.
- [ ] Restore a backup into a clean isolated PostgreSQL database and verify authentication, ownership isolation, missions, workflows, connector metadata, artifacts, and social drafts.
- [ ] Back up durable object storage separately; verify file checksums and restore behavior.
- [ ] Record the date, operator, source backup, target, verification evidence, and rollback decision.
- [ ] Only after the restore drill succeeds, set `SMART_BETHG_BACKUP_RESTORE_VERIFIED=true`.
- [ ] Confirm retention and deletion procedures against actual legal requirements; account deletion is still a request workflow, not an automated deletion engine.

## Organizations and workspace permissions

- [ ] Test organization owner/admin/member/viewer roles with at least two accounts.
- [ ] Test owner-protection, cross-organization access denial, archived workspace denial, and role changes under concurrency.
- [ ] Do not advertise workspace-shared projects/missions/artifacts yet: existing resource APIs remain owner-scoped until their workspace binding and authorization are implemented and reviewed.

## Sandbox execution

- [ ] Keep sandbox disabled unless a trusted image has been reviewed and pinned by digest.
- [ ] Add the exact digest-pinned image to `SMART_BETHG_DOCKER_ALLOWED_IMAGES` and set `SMART_BETHG_SANDBOX_PYTHON_IMAGE` to the exact same value.
- [ ] Run hostile-code tests for timeouts, process forks, output floods, filesystem writes, network access, and container cleanup.
- [ ] Verify Docker daemon privileges and host isolation; prefer rootless Docker or a dedicated runner host.
- [ ] Confirm the API returns 503 when Docker is unavailable or configuration is incomplete.

## Social publishing

- [ ] Keep external publishing disabled until a real platform adapter is implemented.
- [ ] Validate OAuth scopes, token refresh/revocation, provider terms, approval flow, rate limits, idempotency, and ambiguous timeout handling for each platform.
- [ ] Use sandbox/test accounts first; capture successful test post IDs and deletion/rollback evidence.
- [ ] Confirm unconfigured platforms transition to `blocked` rather than pretending a post was published.

## Monitoring and security

- [ ] Verify `X-Request-ID` is present and correlates with logs.
- [ ] Verify admin-only operations endpoints reject ordinary users and do not disclose secrets.
- [ ] Configure alerts for repeated 5xx errors, slow requests, database failure, stale worker heartbeat, queue backlog, and storage capacity.
- [ ] Review CSP report-only violations before planning an enforcing CSP rollout; do not enable enforcement without browser compatibility evidence.
- [ ] Run dependency/secret scanning, the full unit suite, PostgreSQL integration tests, and independent security review on the exact release commit.
- [ ] Exercise CSRF, session revocation, rate limits, owner isolation, organization/workspace roles, connector approval races, and worker crash/replay.
- [ ] Complete privacy and legal review for the actual deployed features and jurisdictions.

## Readiness endpoint

An administrator can call `GET /api/v1/ops/readiness`. A 503 response contains checks that are not ready. This endpoint is a software/configuration gate; it cannot independently prove that a backup exists, can be restored, or that a legal/security review was completed.
