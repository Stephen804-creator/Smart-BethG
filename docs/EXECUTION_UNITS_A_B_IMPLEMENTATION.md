# Units A–B — Execution Architecture and Secure File Import

Status: Unit A and Unit B implementation is present on this branch. Production enablement remains gated on provisioning and verifying the isolated worker/scanner environment.
Date: 2026-10-30

## Unit A — Architecture and security contract

Added:
- `EXECUTION_PLATFORM_ARCHITECTURE.md`: seven agreed backend responsibilities, trust zones, persistent-project versus temporary-compute lifecycle, runtime registry, isolation/network boundaries, storage and deployment shape.
- `EXECUTION_THREAT_MODEL.md`: assets, adversaries, trust boundaries, threat register, security invariants, host-dependent review and incident response.
- `EXECUTION_SECURITY_REQUIREMENTS.md`: normative requirements for upload/import, persistence, execution, supply chain, privacy and verification.
- `FILE_IMPORT_USER_EXPERIENCE.md`: user journey, status language, recovery, privacy and usability trade-offs; this is a product/engineering contract, not a UI implementation.

The architecture defines modular responsibilities, not seven required microservices. Rootless Docker, gVisor and Firecracker remain candidates pending inspection of the actual execution host. No UI has been built.

## Unit B — Implemented secure import path

- PostgreSQL migration 0017 adds quarantine metadata and a private quarantine storage namespace.
- Both legacy `/api/files` and versioned `/api/v1/files` upload routes are protected by a request-body cap before multipart parsing. The middleware uses bounded spooling and two concurrent upload slots per API process; the route separately enforces the per-file limit.
- Uploads are stored privately, receive server-generated SHA-256/size, sanitized display filenames, detected media type, and untrusted declared MIME metadata. Unsupported extensions, invalid UTF-8, empty files and obvious signature mismatches are rejected.
- The quarantine row and durable `file.inspect` job are inserted in one PostgreSQL transaction, so a successful upload cannot be left without its inspection job after a process crash.
- A dedicated file-only entrypoint, `scripts/run_file_worker.py`, claims only `file.inspect` and `file.extract_pdf` jobs. It is separated from the API and agent/provider worker and does not require the session-signing secret or provider credentials.
- The worker verifies the stored SHA-256 and uses ClamAV's bounded INSTREAM protocol. Only an explicit scanner `OK` result can proceed. Malware, invalid content, archive-policy violations and hash mismatches are rejected. Missing scanner, timeout and indeterminate results retry with bounded attempts; they never release content.
- Clean release copies the object to the trusted uploads namespace and creates the normal file row plus released quarantine state atomically. The original quarantine object is cleaned up after successful release. There is no user-facing release/approval endpoint.
- ZIP inspection validates absolute/drive/traversal paths, malformed path segments, symlinks and special files, duplicate normalized paths, encrypted entries, nested archive extensions, entry count, actual decompressed size and compression ratio. It streams decompression to discard and never writes archive paths to disk. The original ZIP can become a stored file but is not automatically extracted.
- PDF parsing runs in the separate file worker, not the API request process. Extraction results are stored separately with owner-scoped access. Migration 0018 queues existing PDF files for worker extraction, and new clean PDF releases enqueue extraction in the release transaction. The API exposes `GET /api/v1/files/{file_id}/extraction-status`.
- Normal file reads, downloads, summaries and indexing are blocked until a file has a trusted `stored` state. Quarantine status/list/delete operations are owner-scoped.
- Added scanner protocol, failure-mode, archive-adversarial, multipart route, upload-limit, durable queue, PDF worker, worker-crash reconciliation and PostgreSQL-backed quarantine/release tests.
- Added `FILE_INSPECTION_OPERATIONS.md` with deployment variables, least-privilege worker configuration, isolation requirements and rollout checks.

## User experience and compatibility

The intended journey is upload once → received/checking → ready after a clean result. Users do not configure scanners or manually approve ordinary safe files. A scanner outage preserves the upload and retries; after the retry budget, it remains quarantined and shows a failed check rather than being treated as safe. Rejected files remain private and can be deleted.

New uploads are not immediately returned as normal file IDs. They appear in the normal file library only after a clean scan. This is an intentional security boundary and requires the client to display background inspection status; no UI/client redesign is included in this PR.

Existing files are not retroactively malware-scanned or moved into quarantine by migration 0018. Their existing downloads remain available. Existing PDFs are queued for worker-based text extraction, so text extraction may be pending until the worker processes them. A future legacy-file malware reclassification must be staged and communicated because it would temporarily restrict access to previously stored files; this PR does not silently change that policy.

## Production acceptance gates (not certified by repository CI)

1. Provision a private ClamAV daemon, keep it off public ingress, configure signature updates and bounded stream/resource limits.
2. Deploy `scripts/run_file_worker.py` as a separate restricted Linux container/host with non-root identity, read-only filesystem, no Docker socket, no host mounts/namespaces/devices, strict CPU/memory/PID/disk/open-file/wall-clock limits, and private-only access to PostgreSQL, object storage and ClamAV.
3. Supply the worker only its database/storage/scanner credentials. Do not supply provider API keys, session-signing secrets or unrelated application secrets.
4. Use shared durable object storage between API and worker. Local filesystem storage is not suitable across separate hosts or replicas.
5. Run the EICAR scanner test in non-production and prove that it is rejected and never appears in the trusted file list. Prove benign text/PDF/ZIP transitions and scanner-outage fail-closed behavior against the deployed ClamAV service.
6. Enforce request-body limits at the public ingress and perform concurrency/load testing. The ASGI concurrency limit is per process, not a global cross-replica quota.
7. Verify object-store ACLs, encryption, backup/restore, quarantine retention, rejected-file deletion and worker recovery on the target host.
8. Update the user-facing client to show received/checking/ready/rejected/delayed status before enabling this upload contract in production.

The repository contains the code and tests for the workflow; it does not provision ClamAV, deploy the file worker, certify OS/container isolation, or verify the production object-storage host. Do not treat a green CI run as host certification or deployment approval.
