# Smart BethG Connector and Plugin Ecosystem

**Created:** 2026-10-10 UTC  
**Last updated:** 2026-10-10 UTC  
**Status:** Architecture and prioritization plan; only the integrations explicitly marked implemented should be treated as usable.

## Connector vs plugin

A connector is the controlled bridge to an external service: it handles account authorization, scopes, data mapping, rate limits, retries, error normalization, and audit records. A plugin is an extension package that can add one or more capabilities. Smart BethG should support both, but a plugin must not receive unrestricted access just because it is installed. Every tool/action remains subject to user identity, policy checks, budget limits, approval, and audit.

## Connector contract

Each production connector should expose:
- A versioned manifest: ID, display name, category, capabilities, supported objects/actions, authentication type, required scopes, and health state.
- A connection lifecycle: OAuth/state validation where relevant, account selection, scope inspection, credential rotation/revocation, disconnect, and account health checks.
- Typed input/output schemas and server-side validation. Do not accept arbitrary endpoint URLs or let a model construct unbounded network requests.
- Explicit read vs write capabilities. Posting content, sending email, editing a repository, changing infrastructure, deleting data, and spending money are distinct capabilities and must not share a broad blanket permission.
- Rate limits, bounded concurrency, usage/cost accounting, provider error normalization, idempotency, and safe handling of unknown external outcomes.
- Owner-scoped data, a secret-vault reference rather than plaintext tokens, redacted logs, and audit events.
- Unit/contract tests with mocked providers plus end-to-end tests against operator-owned test accounts.

## Categories and suggested rollout

### 1. Storage and artifacts
**Initial support:** local storage for development; S3-compatible object storage for shared artifacts. This is the first storage connector, not a general cloud-administration connector. A provider change requires a verified data migration and restore drill.

### 2. Social publishing
**Implemented in this branch:** Facebook Pages OAuth and text-post publishing, guarded by explicit operator configuration and Meta app approval. A separate worker processes durable jobs. Instagram Professional, YouTube, LinkedIn, and X remain separate adapters because their content types, permissions, quotas, review requirements, and error semantics differ.

### 3. Source code and development
Recommended next: GitHub repositories/issues/pull requests, followed by GitLab if user demand warrants it. Use repository-scoped installation/OAuth permissions, explicit repo selection, branch protection awareness, diff previews, tests, and PR-first changes. Never treat a repository token as permission to merge or deploy automatically.

### 4. Documents and productivity
Potential connectors: Google Drive/Docs, Microsoft OneDrive/SharePoint, Google Calendar, Microsoft Outlook Calendar, Gmail/Outlook email, Notion, and task tools such as Linear/Jira/Trello. Start with read/search and draft operations. Sending messages, changing calendars, or deleting documents should require separate action permissions and clear confirmation.

### 5. Communication and support
Potential connectors: Slack, Microsoft Teams, support ticketing, and customer relationship management systems. Scope access to selected workspaces/channels and records; filter private channels and customer data according to each user's granted access.

### 6. Research and web data
Search providers and browser retrieval should be separate connectors with domain restrictions, timeouts, citations, and content-provenance records. Reference URLs supplied to a campaign are not proof that their contents were retrieved.

### 7. Cloud and DevOps
AWS, Azure, DigitalOcean, container registries, monitoring, and deployment platforms are high-risk action connectors. Start read-only for status/logs. Require narrow roles, environment separation, dry-run plans, approval for changes, and a tested rollback. Do not give an AI a broad cloud administrator key.

### 8. Finance and commerce
Payment gateways, invoices, wallets, and billing are separate high-risk connectors. Use provider webhooks with signature verification, idempotent transactions, reconciliation, and strict separation of user funds from platform operating funds.

## Prioritization rule

Do not add ten integrations at once. Select the next connector based on a real user workflow, provider approval effort, operational cost, test-account availability, and the amount of manual work it removes. Complete one vertical slice: connection UI, secure authorization, one useful read/write operation, revocation, audit, tests, documentation, and recovery behavior. Mark it ready only after end-to-end tests pass.

## Multi-instance requirements

Connector credentials and job state must be shared through PostgreSQL and the encrypted credential vault. Artifact/media bytes must use shared object storage. Background jobs require leases and bounded concurrency. Do not keep OAuth tokens, queues, or critical job state only in process memory. If a provider does not support idempotency, use reconciliation before retrying uncertain side effects.

## External provider approval

Smart BethG cannot grant itself access to an external service. The operator must create/own developer apps, configure redirect URIs, accept provider terms, request required permissions, complete verification/app review where required, and test with accounts that represent the intended public users. A green unit test does not mean the provider has approved the application.
