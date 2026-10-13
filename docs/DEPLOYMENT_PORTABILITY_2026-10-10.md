# Smart BethG Deployment Portability Guide

**Created:** 2026-10-10 20:16 UTC  
**Status:** Portable deployment contract; production rollout still has open release gates.  
**Last updated:** 2026-10-10 20:16 UTC

## Principle

Smart BethG is a Python ASGI application, not a Render application. Render may be used as a low-cost test host, but the application must not require Render-specific YAML, APIs, filesystem behavior, or environment conventions. The same app should be deployable on a generic Linux/Python host, DigitalOcean, AWS, Azure, or another compatible platform.

Keep platform-specific commands and resource definitions in optional deployment examples. Application behavior belongs in Python code and explicit environment variables.

## Local development

- Set `SMART_BETHG_ENV=development`.
- PostgreSQL is required locally and in CI; use the repository's `compose.yaml` service for local development.
- Set `SMART_BETHG_STORAGE_ROOT` to a local writable directory if you do not want the default `./storage`.
- Provider keys are optional; without a configured provider, Smart BethG must report that chat is not configured rather than fabricate an AI response.
- Host Python execution is development-only and must not be enabled in production.
- Use a test database and test credentials only. Never point unit tests at a real user's database.

## Single-instance production

A single-instance and multi-instance deployment both use PostgreSQL. The application has no SQLite runtime fallback.

Required configuration contract:

- `SMART_BETHG_ENV=production`
- `DATABASE_URL` set to a PostgreSQL connection string for a dedicated database.
- `SMART_BETHG_SECRET_KEY` set to a long, random, persistent secret. Changing it invalidates signed sessions.
- `SMART_BETHG_SESSION_HTTPS_ONLY=true` behind HTTPS.
- `SMART_BETHG_STORAGE_ROOT` set to a durable writable storage location, or configure a future shared-storage backend when available.
- `SMART_BETHG_REGISTRATION_OPEN=false` until the public-launch gates are approved.
- `SMART_BETHG_ALLOWED_ORIGINS` set to exact trusted browser origins; leave empty if no cross-origin browser client is needed.
- Provider API keys supplied through the host's secret manager/environment, never committed to Git.

Before accepting real users, verify TLS, durable files, PostgreSQL backups, restore tests, monitoring, log redaction, process restart behavior, and rollback. A deployment being reachable is not proof that these controls work.

## Multi-instance production

All application replicas must share the same PostgreSQL database and stable secret/configuration. The database-backed rate limiter and persisted usage budgets are designed to coordinate through PostgreSQL.

**Multi-instance mode is not yet approved.** Before adding a second replica, implement and test all of the following:

1. A storage abstraction with a shared durable backend for user uploads, generated artifacts, and any files referenced by database records.
2. Shared workspace execution or a remote worker system for Git/filesystem/terminal operations. A local per-instance workspace directory is not shared storage.
3. Durable jobs with leases, bounded concurrency, retry rules, idempotency, cancellation, and crash recovery. Do not use an in-memory queue or a process-local job map as the source of truth.
4. Cross-replica tests proving one instance can read/delete another instance's uploaded file and that concurrent budget/rate-limit checks enforce one shared limit.
5. Independent backups and a restore drill for both PostgreSQL and object/file storage.

PostgreSQL alone does not make the filesystem, local workspaces, process memory, or provider calls shared. Do not scale the web process horizontally until these gates pass.

## Reverse proxies and client IPs

Rate-limit keys use the client address supplied by the ASGI request. If the app is behind a reverse proxy, configure the ASGI server to trust forwarded client-IP headers only from known proxy addresses. Do not parse arbitrary `X-Forwarded-For` values in application code or trust user-supplied forwarding headers. Validate that real client IPs are preserved, otherwise many users may share the proxy's rate-limit bucket.

## Generic ASGI process

The application entry point is `main_fastapi:app`. A deployment provider should start it using a supported ASGI server (for example, Uvicorn or Gunicorn with a Uvicorn worker), configure the listening port through the platform's standard mechanism, and expose the health endpoint. The exact process command can live in provider-specific examples, but it must not change the application architecture.

Do not add a mandatory Render manifest or Render SDK to the app. Optional deployment examples should state their assumptions and remain replaceable.

## Release checklist

- [ ] Current-head unit tests, PostgreSQL integration tests, dependency audit, and secret scan are green.
- [ ] Production starts only with PostgreSQL and a persistent secret.
- [ ] Registration remains closed until public-launch review is complete.
- [ ] HTTPS, cookie flags, trusted origins, health checks, and proxy client-IP behavior are verified.
- [ ] Database migration, backup, and restoration are rehearsed on a disposable copy.
- [ ] File storage and workspace behavior are verified after restart/redeployment.
- [ ] Shared object storage and durable workers are complete before multi-instance operation.
- [ ] Monitoring, alerting, log retention/redaction, rollback, load tests, and incident procedures are ready.
- [ ] Terms and Privacy Policy are reviewed and accurately reflect deployed data flows.
- [ ] An independent security review has signed off on tool execution and cross-user boundaries.

This guide is a portability contract and checklist. It is not evidence that a live deployment has already passed these checks.
