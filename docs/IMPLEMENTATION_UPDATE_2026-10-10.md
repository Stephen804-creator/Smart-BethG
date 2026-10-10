# Implementation Update — Social Campaigns, Connectors, and Artifacts

**Created:** 2026-10-10 UTC  
**Last updated:** 2026-10-10 UTC  
**Branch:** feat/social-agent-connectors-2026-10  
**Status:** Implementation in review; do not treat as public-launch approval.

## Delivered in this change

- Added an authenticated social campaign API and focused Social campaigns workspace page.
- Campaigns record objective, audience, tone, reference URLs, content rules, target platforms, timezone, cadence, date range, daily post cap, and autonomy mode.
- AI plan generation reuses Smart BethG's configured provider fallback and token/spend-budget pipeline without adding every generation request to the normal chat history.
- Generated content is parsed and validated in small batches. The service saves the schedule only after all requested batches are valid, avoiding partial calendars.
- Time slots are calculated using an IANA timezone, stored as UTC instants, and checked against the campaign date range and daily posting limit.
- Every scheduled post is versioned and gets a unique idempotency key. Publishing-job states distinguish approval, missing connection, queued work, and cancellation.
- Automatic publishing requires explicit campaign-level authorization. The authorization timestamp and scoped platforms/dates/daily cap are stored, and a security audit event is written.
- Campaign calendars can be exported as verified JSON artifacts.
- Artifact output supports text, Markdown, JSON, Python, JavaScript, HTML, CSV, and YAML text formats, verifies SHA-256 when reading, and uses a storage abstraction with local and S3-compatible backends.
- Added a dry-run-first local-to-object-storage migration script. It verifies checksum before and after upload and updates the database only after verification.
- Added connector catalog metadata for Facebook Pages, Instagram Professional, YouTube, LinkedIn, and X. Missing publisher adapters fail closed instead of reporting false success.
- Added a separate durable worker that claims due PostgreSQL jobs with leases, verifies approval and account state, persists confirmed provider post IDs, blocks missing adapters, and marks unknown outcomes indeterminate instead of blindly retrying. The worker must be run as a separate process; the web app does not silently spawn it.
- Added unit tests for ownership, timezone validation, schedule limits, atomic plan creation, AI JSON failure, artifact format/integrity, and connector fail-closed behavior.

## Explicitly not complete yet

This is not yet the end-to-end autonomous social publisher. Provider-specific OAuth and real publishing adapters have not been implemented; the connector catalog reports them as planned. No post will be published by this branch until an approved platform adapter and active account connection exist. The worker is a first durable queue runner, but production rollout still needs bounded concurrency, provider-specific retry/reconciliation, metrics/alerts, process supervision, and multi-instance load tests before the user can close the browser and trust scheduled publication.

Campaign reference URLs are stored and supplied to the generation prompt, but this implementation does not fetch or verify their contents. The generated content therefore must not claim to have read them. Research/citation verification is a separate integration task.

S3-compatible storage is optional and provider-neutral. Existing local files are not automatically copied when the backend setting changes; follow the storage migration runbook and test restoration before switching a production dataset.

The UI can create a campaign, ask the configured AI provider for a 30-post plan, review posts, inspect connector readiness, and export the calendar artifact. The actual publishing controls are intentionally blocked while integrations are unconfigured.

## Verification required before merge

- Run the unit suite and PostgreSQL integration suite on the latest commit.
- Verify new migration 0003 on a fresh PostgreSQL database and on a database initialized by earlier migrations.
- Verify JavaScript syntax and the social workspace's authenticated flows.
- Test AI generation with no provider, provider errors, budget exhaustion, malformed JSON, and a complete 30-post plan.
- Run cross-user API tests for campaign, post, artifact, and connection records.
- Rehearse local-to-S3 migration and restoration in an isolated environment.
- Do not merge until any red CI checks are fixed and the limitations above remain visible in the PR.

## Timestamp and history rule

This record is dated to make the implementation sequence understandable. The exact commit timestamp and hash in Git are authoritative; failed intermediate CI runs are preserved in Actions history and must not be described as passing.
