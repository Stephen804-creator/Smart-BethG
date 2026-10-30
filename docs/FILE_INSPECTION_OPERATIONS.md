# File Inspection Worker — Deployment and Operations

Status: implementation contract; no scanner service or production worker was provisioned by this change.

## Components

- API: accepts bounded multipart uploads and writes the object to the private `quarantine` namespace.
- PostgreSQL: stores quarantine metadata and a durable `file.inspect` job in the same transaction.
- Inspection worker: run `python scripts/run_worker.py` as a separate service/process. It claims leased jobs, verifies SHA-256, scans through ClamAV INSTREAM, applies ZIP structural/expansion policy, and atomically releases clean files.
- ClamAV: private daemon reachable only from the inspection worker. It must not be exposed to the public internet.
- PDF extraction worker: the same worker process handles `file.extract_pdf` jobs after release and stores bounded text output. This is a separate process from API request handling, but it still requires OS/container isolation in deployment.

## Required environment

| Variable | Default | Meaning |
|---|---:|---|
| `SMART_BETHG_FILE_SCANNER_HOST` | empty | Private DNS name/address of ClamAV daemon. Empty means fail closed. |
| `SMART_BETHG_FILE_SCANNER_PORT` | `3310` | ClamAV daemon TCP port. |
| `SMART_BETHG_FILE_SCANNER_TIMEOUT_SECONDS` | `30` | Connect/read timeout for one scan. |
| `SMART_BETHG_FILE_ARCHIVE_MAX_ENTRIES` | `1000` | Maximum ZIP central-directory entries. |
| `SMART_BETHG_FILE_ARCHIVE_MAX_EXPANDED_BYTES` | `104857600` | Maximum actual decompressed bytes streamed to discard. |
| `SMART_BETHG_FILE_ARCHIVE_MAX_COMPRESSION_RATIO` | `100` | Maximum per-entry expansion ratio. |

The worker also needs the same PostgreSQL schema and access to the configured private object storage. Use a separate worker identity and least-privilege credentials. Do not give the worker provider API keys, session-signing secrets, public ingress, Docker socket access, or access to unrelated project data.

## Isolation requirements

Run the inspection/PDF worker as a separately deployed, restricted container or host with:
- non-root user, read-only root filesystem, no privileged mode, no host PID/network namespaces, no host mounts, no container-engine socket, and no device access;
- strict CPU, memory, PID, open-file, disk, and wall-clock limits;
- private-only network paths to PostgreSQL, object storage, and ClamAV;
- no general outbound internet access;
- bounded temporary storage and log output;
- pinned image digest, reviewed dependencies, SBOM and vulnerability scanning.

The ClamAV daemon must have its own memory/CPU limits, current signature updates, bounded stream size and private network policy. A scanner response other than explicit `OK` is not clean. Scanner failure never releases content.

## State and recovery

- Quarantine upload and inspection-job enqueue are one database transaction.
- Jobs use the existing PostgreSQL lease/retry/idempotency queue.
- Clean inspection copies the object to trusted uploads storage and commits the normal file row plus released quarantine state atomically.
- Malware or archive-policy failures remain quarantined and show rejected status.
- Temporary scanner/worker errors retry with bounded backoff; after the retry budget, the record remains quarantined with failed status. It is not automatically deleted or released.
- User deletion is owner-scoped and allowed only while the quarantine record remains quarantined.
- PDF extraction has its own durable job and status endpoint: `GET /api/v1/files/{file_id}/extraction-status`.
- Migration 0018 queues existing PDF records for worker extraction. Monitor queue depth before/after applying this migration to a large legacy library.

## Rollout checklist

1. Provision ClamAV as a private service and configure signature updates, maximum stream size, resource limits, and network ACLs.
2. Deploy `scripts/run_worker.py` as a separate worker service with least-privilege database/storage access and the scanner host variable.
3. Ensure API and worker use the same durable shared object storage. Local filesystem storage is not suitable across separate hosts or replicas.
4. Apply PostgreSQL migrations and verify migration 0018 completed.
5. Upload the standard EICAR test file in a controlled non-production environment; verify it is rejected and never appears in the normal files list.
6. Verify a benign text/PDF/ZIP file moves through queued → checking → clean/released; verify PDF extraction status transitions pending → ready.
7. Stop ClamAV and verify uploads remain quarantined, retry, and ultimately show failed rather than clean.
8. Test oversized request bodies at the public ingress and under concurrent load.
9. Verify quarantine deletion, retention, backup/restore, object-store ACLs, and worker cleanup.
10. Only then enable the user-facing upload flow in a release after the client has been updated to display background status.

Do not run this worker on the public web service's shared host without a separate isolation review. Repository-level tests cannot certify the deployed host.
