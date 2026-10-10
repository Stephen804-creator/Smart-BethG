# Social Worker Operations

**Created:** 2026-10-10 UTC  
**Last updated:** 2026-10-10 UTC  
**Status:** Operational runbook for the current durable queue runner; platform publishing still requires a configured and approved adapter.

## Process model

The web process serves requests and saves scheduled jobs to PostgreSQL. The social worker is a separate long-running process. It must not depend on a browser session remaining open. It polls the shared queue, claims due jobs with a lease, checks campaign status/post approval/account state, invokes the configured connector, and stores the provider's post ID.

Start command from the repository root and the same virtual environment as the web app:

    python -m workers.social_publisher

Optional environment setting:
- SMART_BETHG_SOCIAL_WORKER_POLL_SECONDS: poll interval, clamped to 1–60 seconds; default 5.

Use a process supervisor (systemd, a container orchestrator, or the host's supported worker process) with automatic restart and centralized logs. Do not launch the worker as a background thread inside each web worker; that would create duplicate pollers and unpredictable lifecycle behavior. Multiple worker processes are safe to claim PostgreSQL jobs through row locks, but multi-instance load testing is still required.

## Required environment

- DATABASE_URL must point to the shared production PostgreSQL database.
- The same database migration set must be applied before starting the worker.
- The social platform app configuration, encrypted credential-vault key, and explicitly enabled publisher adapter must be present for the chosen provider.
- The provider connection must be active and the campaign must be active.
- Shared artifact storage must be configured for multi-instance use. This worker currently publishes text posts and does not upload media.

## Job states

- awaiting_approval: a human review is still required.
- awaiting_connection: approval/authority exists, but a usable account/adapter is missing.
- queued: ready for execution at or after scheduled_at.
- publishing: leased to a worker.
- published: the provider returned a post ID and Smart BethG persisted it.
- blocked: a known precondition or explicit provider rejection prevented publication.
- cancelled / cancel_requested: campaign cancellation has stopped pending work or requested cancellation of an in-flight operation.
- indeterminate: the worker cannot prove whether an external side effect occurred. Reconcile with the provider before retrying.

## Recovery and alerts

Expired publishing leases become indeterminate rather than being automatically replayed. This is deliberate: if the provider accepted a post but the worker crashed before saving the ID, blindly replaying can create a duplicate. A production operator should have a reconciliation screen/job that checks provider state using the account, content, time window, and any provider correlation information before deciding whether a safe retry is possible.

Monitor at minimum:
- Count and age of queued, blocked, and indeterminate jobs.
- Worker process liveness and database connectivity.
- Provider 401/403 permission failures, 429 rate limits, 5xx responses, and timeouts.
- Job lease expiry and repeated failures.
- PostgreSQL connection pool pressure and provider spend/quotas.

Do not log access tokens, OAuth codes, credential references that grant access, full private post content, or raw provider response bodies. Alert on identifiers and normalized error codes instead.

## Production acceptance checklist

- [ ] Worker starts under process supervision after reboot/deploy.
- [ ] A scheduled test post publishes while the browser is closed.
- [ ] A job is processed once across two worker processes.
- [ ] Pause/cancel prevents jobs that have not started.
- [ ] A provider 4xx rejection becomes blocked without a false success.
- [ ] A timeout or 5xx becomes indeterminate and is not automatically replayed.
- [ ] A revoked account blocks future publication.
- [ ] A worker crash after provider acceptance is reconciled without duplicating the post.
- [ ] Metrics/alerts, backup/restore, and deployment rollback have been tested.
