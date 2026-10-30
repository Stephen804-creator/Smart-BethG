# Smart BethG Execution Platform — Implementation Record

**Purpose:** This is the durable hand-off record for Units A–D and the prerequisites for Unit E. Read this before starting later execution-platform work. Update the status here when a requirement is implemented, tested, deployed, deferred, or superseded.

**Current workstream:** PR #27 — Units C–D  
**Branch:** `feature/execution-platform-units-c-d-2026-10-30`  
**Dependency:** PR #26 — Units A–B, branch `feature/execution-platform-units-a-b-2026-10-30`  
**Status:** Application code and repository CI for C–D pass. Production host/runner verification is still outstanding. PRs remain separate drafts; no merge or deployment is implied.

## Status at a glance

| Unit | Scope | Current status |
|---|---|---|
| A | Architecture and security contract | Implemented in PR #26; host-specific choices remain deployment decisions |
| B | Secure file import, quarantine, inspection and extraction pipeline | Implemented in PR #26; production services/client rollout gates remain |
| C | Runtime registry and controlled execution API | Code implemented in PR #27; host/runtime operational verification remains |
| D | Sandbox isolation and cleanup hardening | Code and regression tests implemented in PR #27; actual host isolation verification remains |
| E | Dedicated execution runner and durable job lifecycle | Not started; must be planned against the requirements below |

## Unit A — Architecture and security contract (PR #26)

The architecture establishes the security boundaries for the execution platform:

- Keep persistent project/file storage separate from temporary execution compute.
- Treat uploaded files, generated source, archives, runtime output, and execution requests as untrusted.
- Use a controlled runtime registry; clients must not provide arbitrary images, shell commands, entrypoints, mounts, or environment.
- Default-deny network access from untrusted execution.
- Keep storage access owner-scoped and prevent a runtime from gaining broad application or host access.
- Define trust zones, threat model, and host-dependent security gates.
- Preserve the seven backend responsibilities as logical boundaries; they do not require seven separate microservices.
- Rootless Docker, gVisor, or Firecracker selection is not certified by architecture documentation alone. Evaluate the actual host and threat model before production.

## Unit B — Secure file import (PR #26)

### Implemented application behavior

- Store quarantine metadata in PostgreSQL and file bytes in private quarantine storage.
- Protect both legacy `/api/files` and versioned `/api/v1/files` upload routes with request-body limits before multipart parsing, bounded spooling, and per-file limits.
- Calculate SHA-256 and size on the server; sanitize filenames; validate supported extensions, signatures, and UTF-8 where applicable. Declared MIME type is untrusted metadata, not proof of file type.
- Commit quarantine metadata and a durable `file.inspect` job in one PostgreSQL transaction.
- Run inspection in a dedicated file-only worker (`scripts/run_file_worker.py`) that claims only registered file job types, separate from API and agent/provider workers.
- Use a fail-closed ClamAV INSTREAM client. Only an explicit supported clean verdict permits release. Scanner absence, timeout, malformed response, or indeterminate verdict must retry or remain blocked; none may be treated as clean.
- On clean verdict, create the ordinary file record and released quarantine state atomically, then clean up the quarantine object. No manual user release endpoint.
- Inspect ZIP archives without extracting members to disk. Reject unsafe paths, symlinks/special files, duplicates, encrypted entries, nested archives, excessive entry counts, actual expansion, and suspicious compression ratios.
- Move PDF parsing to a separate durable worker and store bounded extraction results. Legacy PDFs are queued for background extraction; new clean PDFs enqueue extraction during release.
- Block non-ready file reads, downloads, extraction, and search until trusted status.
- Expose quarantine and PDF extraction status. Public quarantine responses use a distinct `quarantine_id`, not a trusted `file_id`, and omit private storage locators and internal owner IDs.
- Provide owner-scoped retry after failed quarantine checks without requiring re-upload.
- Reconcile inspection/PDF jobs abandoned by killed workers so records do not remain stuck after lease exhaustion.
- Validate scanner/worker timeouts and ZIP entry, expansion, and compression-ratio configuration bounds.
- Include tests for scanner fail-closed behavior, adversarial archives, multipart routes and middleware, queue isolation, PDF worker behavior, worker-crash recovery, and PostgreSQL-backed quarantine/release.

### Compatibility and UX decisions to preserve

- A new upload is a quarantine record first. It enters the normal file library only after a clean inspection.
- The client must communicate received, checking, ready, rejected, and delayed states. Do not expose scanner/security complexity to the user; present simple understandable statuses.
- A failed or delayed check should be retried internally where appropriate. Users should not have to upload the same file again just because a worker/scanner was temporarily unavailable.
- Existing stored files are not retroactively malware-scanned or moved into quarantine by PR #26. Existing downloads remain available. Existing PDFs are queued for background text extraction; extraction may remain pending until the worker processes them.
- Any future legacy-file malware reclassification must be staged because it could temporarily restrict access to previously stored files.

### Unit B production rollout gates

- Provision a private ClamAV service and deploy the file-only worker in a restricted Linux container/host with no public ingress, no Docker socket/host mounts, non-root identity, strict CPU/memory/PID/disk/open-file/wall-clock limits, and private-only database/storage/scanner access.
- Configure ClamAV `StreamMaxLength` to at least the maximum application upload size. Keep the daemon private and resource-limited.
- Do not give the file worker provider API keys, session-signing secrets, or unrelated application secrets.
- Use shared durable object storage between API and worker; local disk is not suitable across hosts/replicas.
- Run deployed EICAR, benign text/PDF/ZIP, scanner-outage, ingress-size, load, backup/restore, and worker-recovery checks.
- Update the client to show inspection state before enabling this upload contract for production users.
- CI cannot certify deployed scanner availability, shared-storage durability, or OS/container isolation.

## Unit C — Runtime registry and controlled execution API (PR #27)

### Implemented

- Application-owned, version-controlled runtime registry.
- Requests select a stable runtime ID only. They cannot choose an image, shell command, entrypoint, mount, or environment.
- Python is the only registered runtime in this increment. Do not imply that other languages are supported.
- A runtime is enabled only when the feature flag is enabled, its image has a complete lowercase SHA-256 digest, and that exact image is in the operator allowlist.
- Authenticated `GET /api/v1/sandbox/runtimes` and `POST /api/v1/sandbox/execute` endpoints.
- Existing Python execution endpoint is preserved.
- Runtime listing does not disclose image references or internal environment-variable names.
- Runtime images must be reviewed and pinned. Each additional language needs a fixed invocation, dependencies, resource profile, provenance, and adversarial tests before registration.

### C completion boundary

The registry and API code are implemented. Production readiness still depends on selecting and configuring the actual execution host, approved image, and rootless runtime environment, then testing them there.

## Unit D — Sandbox isolation and cleanup hardening (PR #27)

### Implemented

- No image pulls during execution.
- Network disabled; private IPC.
- Read-only root filesystem and read-only source mount.
- Dropped Linux capabilities, no-new-privileges, and fixed non-root container identity.
- Bounded shared memory and temporary storage.
- CPU, memory, swap, PID, open-file, file-size, core-dump, wall-clock, and combined stdout/stderr output limits.
- Docker log-driver persistence disabled to avoid unbounded user-output persistence.
- Production execution fails closed unless Docker reports rootless mode.
- Post-run container-absence verification. Cleanup failures or daemon uncertainty are not treated as successful removal.
- Regression tests cover registry selection, digest allowlisting, Docker policy, rootless detection, and cleanup behavior.

### D completion boundary

The application-side restrictions and regression tests are implemented. They do not prove the real host is isolated. Before production, verify rootless Docker, kernel capabilities, seccomp/AppArmor policy, filesystem/mount behavior, cgroup enforcement, daemon permissions, and cleanup behavior on the actual execution host. Do not weaken the rootless requirement merely to make execution work on the hosted web application.

## CI verification recorded for PR #27

Latest recorded head: `1fdb1c6d72cc2012321a567e0c247c13149eef15`.

- Python compilation: passed.
- Workspace dashboard JavaScript syntax check: passed.
- Unit test workflow: passed.
- PostgreSQL integration workflow: passed.
- Dependency vulnerability audit: passed after updating the cryptography constraint.
- Secret scan: passed.

These checks validate repository code and automated tests only. They are not a production host certification or deployment approval.

## Unit E — Required next stage (not started)

Do not start E by simply adding a queue around the current synchronous API-to-local-Docker path. E must turn the sandbox into a separately operated execution service.

The E design/implementation must cover:

1. **Dedicated runner boundary:** provision a separate rootless execution host or isolated runner service. The web/API process must not become the untrusted-code execution host.
2. **Authenticated runner communication:** define service identity, authentication, authorization, request signing or equivalent integrity controls, replay protection where appropriate, and private network access.
3. **Durable job lifecycle:** persist queued, claimed, running, succeeded, failed, timed-out, cancelled, and cleanup-pending states; make transitions atomic and recoverable after process/host restarts.
4. **Worker isolation:** runner workers claim only execution jobs, use least privilege, and cannot access unrelated application/provider secrets or other users' data.
5. **Concurrency and quotas:** enforce global and per-user concurrency, CPU/memory/storage/time budgets, queue limits, abuse controls, and fair scheduling across multiple API instances.
6. **Cancellation and deadlines:** cancellation must reach and stop the actual process/container, not merely mark a database row cancelled. Enforce hard deadlines.
7. **Project snapshot input:** provide a safe, immutable, owner-authorized snapshot of the selected project/files to the runner. Do not mount the whole application workspace or arbitrary host paths.
8. **Artifact/output transfer:** return bounded stdout/stderr, exit status, structured metadata, and generated artifacts through authenticated, size-limited transfer into approved storage. Verify ownership and content metadata.
9. **Cleanup and reconciliation:** guarantee or detect removal of containers, temporary files, mounts, and abandoned work after success, failure, timeout, cancellation, or runner crash. Add periodic reconciliation.
10. **Observability and audit:** record job IDs, runtime ID/digest, owner scope, timestamps, resource usage, termination reason, and cleanup outcome without logging secrets or unrestricted user source/output.
11. **Operational readiness:** health checks, runner registration/heartbeat, capacity/drain behavior, deployment configuration, backups where needed, alerts, and documented recovery procedures.
12. **End-to-end validation:** test multiple API instances, concurrent users, malicious source, network-denial attempts, resource exhaustion, oversized output/artifacts, cancellation, runner loss/restart, storage failure, and cross-user isolation.

### Explicit non-goals / safety rules

- Do not expose arbitrary shell execution or user-selected container images.
- Do not enable more languages just because a base image exists.
- Do not allow runtime network access by default.
- Do not put the runner on the public web/API host as a shortcut.
- Do not treat passing CI as proof of production isolation.
- Do not merge/deploy C–D or begin E on the assumption that host prerequisites are satisfied.

## Handoff checklist before E

- [ ] PR #26 (A–B) reviewed and merged in the intended order, without collapsing its separate review history.
- [ ] PR #27 (C–D) reviewed against this record and merged only after its code review gates pass.
- [ ] Private ClamAV, restricted file worker, shared durable storage, and client upload-status experience are provisioned and verified for B.
- [ ] Dedicated rootless execution host/runner selected and provisioned for C–D.
- [ ] Host-level security controls and approved Python image digest verified on that host.
- [ ] End-to-end execution, cleanup, and cross-user isolation tests pass on the real runner.
- [ ] E design explicitly covers all twelve requirements above before implementation begins.

**Last updated:** 2026-10-30  
**Rule:** When work resumes, read this document and inspect the current PR/branch state first. Update this record as requirements are completed; do not silently mark deployment gates complete based on source-code tests.
