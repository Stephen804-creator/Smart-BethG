# Units 21–24 implementation notes

Status: implementation branch only. CI and deployment verification must pass before merge; this document is not a production launch approval.

## Unit 21 — Scheduled and recurring agent jobs

Implemented:
- Authenticated owner-scoped schedule creation, listing, pause, resume, and cancellation.
- Schedules target an existing workflow owned by the same account. Workflows must be validated before scheduling.
- One-off schedules and recurring intervals from 60 seconds to 30 days, with optional maximum run counts.
- Worker polling dispatches due schedules to the existing durable workflow queue.
- Schedule occurrence, workflow run, queue message, and next-run advancement are committed transactionally.
- A unique occurrence-to-workflow-run link and stable queue idempotency key prevent duplicate dispatch under normal multi-worker races.
- A workflow that is no longer validated causes its due schedule to pause rather than silently run.
- New schedules are disabled from arbitrary command execution: they only dispatch existing validated Smart BethG workflows.

Operational boundary:
- The worker must be deployed as a separately supervised process. Missed recurring intervals are coalesced by advancing the next run from processing time rather than creating an unbounded catch-up storm.
- This does not yet provide a cron-expression editor, per-schedule timezone calendar UI, workflow compensation, or user-facing delivery notifications.

## Unit 22 — Capability extensions and developer SDK

Implemented:
- A Python SDK builder for versioned declarative extension manifests.
- Bounded action definitions with typed fields, required fields, risk labels, and explicit side-effect declarations.
- Owner-scoped manifest storage and version uniqueness.
- New manifests begin in draft; an administrator must explicitly approve or disable them.
- Unknown fields, duplicate action names, unsupported types, and unsafe undeclared side effects are rejected.
- Manifests are data contracts only. The platform does not import or execute extension-supplied Python, shell commands, URLs, or module paths.

Operational boundary:
- Approval does not magically create an executable adapter. A trusted built-in or separately reviewed adapter must implement an approved capability before it can run.
- External developer portal, API-key management, signing/attestation, extension distribution, sandboxed third-party runtime, billing, and compatibility certification remain future work.

## Unit 23 — Usage intelligence and fairness

Implemented:
- Account usage summaries aggregate request count, input/output tokens, estimated cost, model/provider breakdown, and daily capacity.
- Plan-specific daily request limits are enforced inside the same database transaction as usage reservations.
- The per-user daily fairness counter uses a conditional PostgreSQL upsert so concurrent API replicas cannot exceed the configured plan request ceiling.
- First-use counters seed from existing same-day reservations to avoid resetting the quota at rollout.
- Plan status is checked before a provider budget reservation is accepted.

Operational boundary:
- Costs are estimates based on the existing pricing catalogue, not invoices from providers.
- No opaque user profiling or cross-account disclosure is introduced. Model/provider details are available only to the authenticated account.
- The existing global/user token and spend budgets remain additional controls; a plan's daily request quota does not replace them.
- Long-term analytics exports, team-level allocation policies, anomaly alerting, and external billing reconciliation remain future work.

## Unit 24 — Plans, credits, rewards, and retention foundations

Implemented:
- Explicit Free, Starter, Pro, and Team plan metadata with daily request limits and monthly credit allowances.
- Admin-only plan assignment and status changes. These are operational controls, not a payment processor.
- Append-only credit ledger with per-user idempotency keys and transactionally protected debits.
- Credits cannot be spent below zero; repeated debit/grant requests with the same key do not apply twice.
- Reward requests are pending by default. Admin review is required before approved rewards create ledger credits.
- Account overview exposes plan metadata, internal credit balance, reward history, and a clear indication that payment processing is not configured.

Commercial boundary:
- Credits are internal capacity units in this release; they are not cash, transferable value, or proof of a paid subscription.
- No checkout, card collection, payment webhooks, refunds through a payment provider, referral abuse detection, or automatic monthly renewal is implemented.
- Do not advertise paid plans as purchasable until a payment provider, webhook verification, subscription lifecycle, tax/legal review, and reconciliation are implemented and tested.
- Monthly credit allowance is plan metadata only; recurring credit grants are not automatically issued by this change.

## APIs added

- POST/GET /api/v1/scheduled-jobs; PATCH /api/v1/scheduled-jobs/{schedule_id}
- POST/GET /api/v1/extensions; POST /api/v1/extensions/{extension_id}/review (admin)
- GET /api/v1/usage/summary?days=30
- GET /api/v1/commercial/overview
- POST /api/v1/commercial/plans/assign (admin)
- POST /api/v1/commercial/credits/grant (admin)
- POST /api/v1/commercial/credits/consume
- POST /api/v1/commercial/rewards
- GET /api/v1/commercial/rewards/pending and POST /api/v1/commercial/rewards/{reward_id}/review (admin)

All mutating browser-session requests continue to require the application's CSRF token.

## Verification and merge gates

- Unit tests are added for scheduling/idempotency, owner isolation, declarative SDK validation, credit-ledger idempotency, reward review, usage privacy, and plan quota enforcement.
- CI must execute the full unit suite, PostgreSQL integration suite, Python compilation, and security checks on the exact PR head.
- Verify recurring dispatch with two worker processes against disposable PostgreSQL and confirm one workflow run per schedule occurrence.
- Test concurrent quota reservations and concurrent credit debits against PostgreSQL.
- Do not merge this stacked PR into the default branch before PRs #13, #16, #17, and #18 are integrated in dependency order.
