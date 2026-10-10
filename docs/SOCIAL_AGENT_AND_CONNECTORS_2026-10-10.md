# Smart BethG Social Agent and Connector Plan

**Created:** 2026-10-10 UTC  
**Last updated:** 2026-10-10 UTC  
**Status:** Architecture and initial API implementation; not yet an end-to-end publishing integration.

## Intended user experience

A user connects an eligible social account through the provider's official OAuth flow, chooses the pages/channels they own, and asks Smart BethG for a campaign—for example, thirty days of educational posts. In the campaign workspace, the user sets the goal, platforms, audience, language/tone, timezone, schedule/cadence, reference links/files, excluded topics, per-day limit, and autonomy level. The agent may propose sensible defaults and ask only for missing decisions that materially affect the campaign. The campaign workspace should stay focused: objective, schedule/calendar, post review, connected accounts, run status, and a concise activity log—not a second general-purpose chat room.

The agent researches/uses approved references, prepares a calendar, generates platform-specific content, checks factual claims and platform limits, stores versioned posts and supporting artifacts, and reports what is scheduled, blocked, published, or failed. A durable worker must continue while the user is offline. Users need pause/resume/cancel, edit-before-publication, retry/reconciliation, timezone-aware scheduling, per-platform outcomes, and notifications.

## Authority and safety model

- Default is review_each_post: no post is published merely because it was generated or scheduled.
- auto_publish_after_campaign_approval requires explicit campaign-level authorization. That authorization must be scoped to selected platforms, accounts, campaign, time window, daily cap, and the exact kinds of external actions allowed.
- Approval to publish must not imply permission to send messages, delete content, follow/unfollow accounts, spend money, or change account settings.
- If content changes after approval, require a new approval.
- Re-check account ownership, provider scopes, current permissions, campaign status, and job idempotency immediately before publication.
- Store only a credential-vault reference in social account rows. Token ciphertext lives in the dedicated credential-vault table, encrypted with a Fernet key supplied outside the database. Never store tokens in campaign rows, logs, source files, or API responses. A KMS/managed-secret backend and automated key rotation remain future hardening tasks.
- Treat a post timeout as an indeterminate outcome until the provider is queried. Do not blindly retry a potentially successful external post.
- Respect provider rate limits, media constraints, user revocation, account disconnection, and current platform terms.

## Current implementation in this branch

- Versioned PostgreSQL migration plus SQLite test schema for campaigns, connected-account metadata, and durable publish-job records.
- Owner-scoped campaign APIs, validated IANA timezones and timezone-aware timestamps, selected-platform enforcement, bounded batch size, per-day limits, and atomic post-batch creation.
- Post drafts retain version history and receive unique idempotency keys.
- Connector catalog and an explicit publisher interface.
- A separate durable worker claims due PostgreSQL jobs with leases, verifies campaign/post/account state, records confirmed success, blocks missing connectors, and marks unknown provider outcomes indeterminate rather than blindly retrying.
- Meta OAuth connection flow for Facebook Pages, with state verification, required permission checks, pending Page selection, owner-scoped activation/disconnection, and encrypted token storage in the credential vault.
- Facebook Pages text-post publisher, opt-in only when the operator configures the Meta app, token-encryption key, and explicit publishing-enabled flag. The adapter is text-only and is not an Instagram publisher.
- Artifact service supports text, Markdown, JSON, Python, JavaScript, HTML, CSV, and YAML text outputs plus bounded binary image/audio/video/PDF/ZIP/generic outputs. It verifies SHA-256 on reads, has owner-scoped local/S3-compatible storage, and exposes a home-page library for create/upload/list/download/delete. Binary uploads are capped at 25 MiB; streaming/multipart media and direct persistence from every generation provider remain open. See `docs/STAGE3_FILES_AND_ARTIFACTS_ACCEPTANCE_2026-10-10.md`.
- Instagram, YouTube, LinkedIn, and X OAuth/publishing adapters remain planned. Facebook's app review and a real test-account end-to-end run are still external release gates. The existence of an adapter does not prove that Meta has approved the app or its permissions.

## Connector delivery sequence

1. Shared connector contract: capabilities, auth status, health, publish result, rate-limit response, retryability, idempotency, and provider error normalization.
2. Extend account authorization from Facebook Pages to other providers with OAuth state/PKCE where supported, least-privilege scopes, callback configuration, refresh/revocation, encrypted secret storage, and disconnect/delete flows.
3. Expand Facebook support beyond text only, then add Instagram Professional publishing with media validation; verify each provider's current API permissions and app-review requirements using official provider documentation.
4. Harden and deploy the durable worker: PostgreSQL job leases/claims, bounded concurrency, provider-specific retry rules, dead-letter/reconciliation states, metrics, and multi-instance safety. The first worker is present, but operational hardening is not complete.
5. Additional adapters: add one provider at a time, each with sandbox/contract tests and a documented capability matrix.
6. End-to-end acceptance: connect a test account, create a multi-day campaign, leave the browser closed, observe scheduled publication, test pause/cancel, revoke access, simulate provider timeouts, and prove that duplicate posts are not created.

## Portability

Keep connectors provider-neutral. Credentials are supplied through standard environment configuration/secret-manager adapters; object storage supports local development or an S3-compatible backend. Do not add Render-only assumptions. A compatible ASGI deployment and independent worker process should be deployable on a generic Linux host, DigitalOcean, AWS, Azure, or another compatible provider.

## External prerequisites

The operator must create/own the provider developer apps and complete each platform's current approval/review process. Smart BethG cannot grant itself Facebook, Instagram, YouTube, LinkedIn, or X publishing permission. Provider pricing, scopes, app-review rules, quotas, and allowed post types must be verified against current official documentation at implementation time.