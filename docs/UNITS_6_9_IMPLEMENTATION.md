# Units 6–9 implementation notes

**Updated:** 2026-10-24  
**Branch:** `feature/units-6-9-connectors-queue-missions-2026-10-24`

## Unit 5 prerequisite: typed capability registry

A trusted code-defined registry describes connector actions, accepted argument types, required fields, permission identifiers, and risk levels. Unknown actions and unknown arguments are rejected. This is the minimum contract needed for Units 6–9; it does not yet provide a public third-party SDK or versioned remote manifests.

## Unit 6: connector platform

- Authenticated API endpoints expose a connector catalog, create/list/disconnect owner-scoped installations, and request registered actions.
- Installations store granted permission names, not raw access tokens. The optional `credential_ref` field is intended for a trusted secret-manager reference and is never returned by the user API.
- A trusted adapter registry is the only execution route. A small built-in Smart BethG knowledge-search adapter provides a real read-only vertical slice.
- GitHub, Google Drive, and Slack are catalog contracts only. They have no live OAuth/token lifecycle or trusted runtime adapter in this branch, so they cannot execute actions yet. A catalog entry is not a connected integration.

## Unit 7: policy and approvals

- Unknown capabilities, wrong owners, missing permissions, and disconnected external connectors are denied.
- Registered read-only actions may run when policy allows. Side-effecting/write/destructive/financial actions create durable approvals.
- Approval execution revalidates the installation, capability, permission, and policy; an atomic claim prevents duplicate approval requests from executing the same operation twice.
- Legacy direct host filesystem/Git/terminal/network/Docker execution remains disabled. This work does not re-enable it.

## Unit 8: durable jobs

- PostgreSQL stores jobs, idempotency keys, attempts, priorities, leases, errors, and results.
- Run creation and initial job insertion happen in the same database transaction.
- Workers claim jobs with row locks, use a lease token to guard completion, retry transient failures with bounded exponential backoff, and stop after a configured attempt limit.
- The API exposes owner-scoped job status and cancellation for queued jobs.
- Run the worker as a separate process with the same database configuration: `python scripts/run_worker.py`.
- Execution is **at least once**, not exactly once. Trusted connector adapters must honor the supplied idempotency key for side-effecting operations. A lease does not prove a timed-out external operation did not complete.

## Unit 9: mission execution

- Missions can store up to 25 validated connector-action steps, with a 100 KB plan bound.
- Starting a mission run writes the run and its queue job in one transaction.
- The worker runs steps in order, persists progress, stops on failure, and pauses a mission when a step requires approval. A successful approval resumes at the next step.
- A mission without a step plan fails clearly with `plan_required`; natural-language planning is not claimed to be implemented.
- A failed external action is not automatically compensated. Saga/compensation, human recovery for indeterminate side effects, and natural-language plan generation remain future work.

## Verification and release gates

CI must pass the full unit suite, PostgreSQL integration job, dependency audit, and secret scan. Before production use, add multi-worker lease-expiry/replay tests, end-to-end approval/resume tests, provider-specific OAuth/scope checks, secret-manager integration, and live connector adapter tests. Do not enable horizontal scaling until the worker and shared-storage recovery tests pass.
