# Smart BethG Production-Readiness Root-Cause Plan

**Created:** 2026-10-27  
**Base:** `main` at `b20e38bf987ba97e062947c87aa6e7d0d1c681f5`  
**Status:** Investigation plan; this document is not evidence that the listed checks have passed.

## Operating rules

- Reproduce a defect before changing code whenever practical.
- Record the failing test, log, request, or code path that supports each finding.
- Fix the smallest responsible layer; avoid unrelated refactors and feature expansion.
- Add a regression test for every corrected bug.
- Run relevant tests after each focused change, then run the full suite.
- Never report a test, security scan, browser flow, or deployment check as passing unless it actually ran and passed.
- Keep changes on this branch or a dedicated fix branch. Do not force-push, bypass required checks, or merge stacked PRs out of dependency order.
- Do not expose credentials, private user data, raw session cookies, or unredacted logs in reports.

## Confirmed repository facts from the initial inspection

1. The default branch is `main`, currently observed at `b20e38bf987ba97e062947c87aa6e7d0d1c681f5`.
2. PR #13 and PR #15 are merged into `main`.
3. PR #16 is a stacked Units 10–15 implementation branch. Its own description reports a previously fixed generated-ID table registration issue and states that CI passed on its recorded head; current-head verification must be refreshed before relying on that claim.
4. PR #17 is the hardening follow-up for PR #16 and is marked merged in the latest connector response, but its changes are not thereby proven to be on `main`; inspect its base/head and merge ancestry before deciding what to integrate.
5. PR #18 contains Units 16–20 and has been described as depending on the Units 10–15 hardening work. Confirm its current base, merge ancestry, and exact head before integration.
6. PR #19 is reported merged into the Units 16–20 feature branch, not directly into `main`. Verify ancestry so its work is not accidentally omitted or duplicated.
7. PR #14 is a UI/UX draft. Its branch comparison against `main` reported divergence (40 commits ahead and 62 behind at the time of inspection). Do not merge it blindly; rebase/cherry-pick or recreate a focused UI branch only after inspecting the current diff and resolving conflicts.
8. The README explicitly says Smart BethG is not cleared for unrestricted public launch. It lists remaining gates involving account/privacy controls, production connector validation, storage/scaling, worker operations, security review, and backup/restore verification.
9. The repository's README requires PostgreSQL and documents that local storage is not shared across multiple application replicas.
10. A successful Railway status check was visible for the inspected main commit, but that is not equivalent to complete application, worker, security, or end-to-end verification.

## Work units

### Unit A — Establish the real branch and CI state
- Fetch current metadata for `main`, PRs #14, #16, #17, #18, and #19.
- Compare each head with its base and with `main`; identify missing commits, duplicate commits, and unsafe merge order.
- Retrieve current workflow runs and combined statuses for the exact candidate commits.
- Distinguish a runner failure (no steps executed) from a real test failure.
- Deliverable: branch ancestry table and current CI evidence.

### Unit B — Reproduce backend and database failures
- Inspect app startup, route registration, dependency wiring, PostgreSQL migrations, schema registration, and worker entry points.
- Run Python compilation, unit tests, and PostgreSQL integration tests on a disposable database.
- Check fresh-install migration and upgrade-from-previous-schema paths separately.
- Deliverable: issue-by-issue reproduction notes and regression tests.

### Unit C — Workflow, queue, and specialist reliability
- Test idempotent step replay after a simulated worker interruption.
- Test duplicate claims with concurrent workers, stale leases, failed child missions, and workflow completion aggregation.
- Confirm ambiguous provider calls are not automatically repeated where doing so could duplicate cost or side effects.
- Verify queue payloads are bound to the expected workflow step and owner.
- Deliverable: reproducible tests for each failure and targeted fixes.

### Unit D — Auth, tenant isolation, export, and security
- Test owner/workspace isolation on every relevant read/write path.
- Review session invalidation, CSRF, cookie configuration, secrets, rate limiting, and authorization checks.
- Test export allowlists and nested sensitive-key filtering; confirm deletion requests are not represented as completed deletion.
- Run dependency/secret/security checks that are available and record any tools that could not execute.
- Deliverable: prioritized security findings and verified remediations.

### Unit E — Files, artifacts, and multi-instance safety
- Test path traversal, symlinks, upload size enforcement, media-type validation, ownership checks, and download/delete authorization.
- Verify configured storage survives restart. Do not enable horizontal scaling until shared durable storage and cross-replica visibility are proven.
- Deliverable: storage regression tests and documented deployment requirements.

### Unit F — UI/UX and browser verification
- Reconcile PR #14 with the current application without discarding newer work.
- Check Jinja template rendering, navigation destinations, chat pending/retry behavior, onboarding first-visit and returning-user flows, keyboard access, and responsive layouts.
- Verify controls do not advertise unavailable integrations or actions.
- Add or run browser tests where the repository/environment supports them.
- Deliverable: UI issue list, fixes, and browser evidence.

### Unit G — Deployment and operational recovery
- Verify environment-variable validation, health/readiness endpoints, worker supervision, database connection/TLS configuration, logs, request correlation, and failure handling.
- Require a real backup/restore drill before treating the backup attestation as satisfied.
- Test deployment restart and database migration procedure in a non-production environment.
- Deliverable: deployment verification report and remaining operator-owned gates.

### Unit H — Release decision
- Run the complete applicable test suite and inspect the exact commit intended for release.
- Review diff for secrets, accidental data changes, unsafe migrations, and unrelated modifications.
- Publish a release checklist listing passed checks, failed checks, skipped checks, and manual gates.
- Do not label the app production-ready while a critical/high-risk gate remains unresolved.

## Priority order

1. Current branch ancestry and current-head CI evidence.
2. Critical security, data integrity, startup, and workflow correctness defects.
3. Regression tests and narrowly scoped fixes.
4. UI/UX merge reconciliation and browser verification.
5. Deployment, recovery, and launch-gate evidence.

## Findings ledger

| ID | Finding | Evidence | Status |
|---|---|---|---|
| SB-PROD-001 | UI branch diverged significantly from main; blind merge risks conflicts or regression. | PR #14 branch comparison against main. | Confirmed branch-risk; root cause of any UI bug not yet established. |
| SB-PROD-002 | PR dependency/ancestry needs reconciliation before release. | PR descriptions and current base/head metadata for #16–#19. | Investigation required. |
| SB-PROD-003 | Public launch is explicitly blocked by documented operational/security/privacy gates. | README and production launch checklist. | Confirmed release constraint; individual gates require fresh evidence. |
| SB-PROD-004 | Successful status check on main does not establish end-to-end production readiness. | Main combined status and documented test boundaries. | Confirmed verification limitation. |

Add each new defect with a reproduction, root cause, fix commit, regression test, and verification result. Do not mark an item fixed until the regression test passes.
