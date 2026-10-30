# File Inspection Worker — Deployment and Operations

Status: implementation contract. The repository contains the worker and scanner client; no scanner service or production worker was provisioned by this change.

## Components

- API: accepts bounded multipart uploads and writes original bytes to private quarantine storage.
- PostgreSQL: stores quarantine metadata and the durable `file.inspect` job in one transaction.
- File-only worker: run `python scripts/run_file_worker.py` as a separate, restricted service. It claims only `file.inspect` and `file.extract_pdf` jobs; it does not load agent/provider handlers.
- ClamAV: private daemon reachable only from the file worker. It must not be exposed to the public internet.
- PDF parser: runs in the file worker after the file has passed malware inspection. It writes bounded extracted text to PostgreSQL; the API reads the result and does not parse PDFs in a request.

## Required environment

| Variable | Default | Meaning |
|---|---:|---|
| `SMART_BETHG_PROCESS_ROLE` | `web` | File worker entrypoint sets this to `file-worker`; production web/agent workers still require the session secret. |
| `SMART_BETHG_FILE_SCANNER_HOST` | empty | Private DNS name/address of ClamAV. Empty means fail closed. |
| `SMART_BETHG_FILE_SCANNER_PORT` | `3310` | ClamAV daemon TCP port. |
| `SMART_BETHG_FILE_SCANNER_TIMEOUT_SECONDS` | `30` | Connect/read timeout for one scan. |
| `SMART_BETHG_FILE_INSPECTION_JOB_TIMEOUT_SECONDS` | `120` | Per-job wall-clock alarm in the Linux worker. Container CPU/memory/disk limits are still required. |
| `SMART_BETHG_FILE_ARCHIVE_MAX_ENTRIES` | `1000` | Maximum ZIP central-directory entries. |
| `SMART_BETHG_FILE_ARCHIVE_MAX_EXPANDED_BYTES` | `104857600` | Maximum actual decompressed bytes streamed to discard. |
| `SMART_BETHG_FILE_ARCHIVE_MAX_COMPRESSION_RATIO` | `100` | Maximum per-entry expansion ratio. |

The file worker also needs the same PostgreSQL schema and access to the configured private object storage. Use a separate worker identity and least-privilege credentials. Do not give it provider API keys, session-signing secrets, public ingress, Docker socket access or access to unrelated project data.

## Isolation requirements

Run the file worker as a separately deployed restricted Linux container or host with:
- non-root user, read-only root filesystem, no privileged mode, no host PID/network namespaces, no host mounts, no container-engine socket and no device access;
- strict CPU, memory, PID, open-file, disk, temporary-storage and wall-clock limits;
- private-only network paths to PostgreSQL, object storage and ClamAV;
- no general outbound internet access;
- bounded log output;
- pinned image digest, reviewed dependencies, SBOM and vulnerability scanning.

The process alarm is a second line of defense, not a substitute for cgroups/container resource controls. ClamAV must have its own memory/CPU limits, current signature updates, bounded stream size and private network policy. A scanner response other than explicit `OK` is not clean.

## State and recovery

- Quarantine upload and inspection-job enqueue are one database transaction.
- Jobs use the existing PostgreSQL lease/retry/idempotency queue. Each worker claims only the job types it has registered.
- Clean inspection copies the object to trusted uploads storage and commits the normal file row plus released quarantine state atomically. The quarantine copy is then deleted; cleanup failure is logged for operations follow-up.
- Malware or archive-policy failures remain quarantined and show rejected status.
- Temporary scanner/worker errors retry with bounded backoff; after the retry budget, the record remains quarantined with failed status. The owner can request another bounded inspection attempt after the service is restored; it is not automatically deleted or released.
- User deletion and retry are owner-scoped. Retry is available only for a failed inspection and creates a new idempotency generation; it does not bypass scanning or release the file.
- PDF extraction has its own durable job and status endpoint: `GET /api/v1/files/{file_id}/extraction-status`.
- Migration 0018 creates extraction state and queues existing PDFs for background text extraction. It does not retroactively malware-scan legacy stored files. Monitor queue depth before/after applying this migration to a large library.

## Rollout checklist

1. Provision ClamAV as a private service and configure signature updates, maximum stream size, resource limits and network ACLs.
2. Deploy `scripts/run_file_worker.py` as a separate restricted service with least-privilege database/storage access and the scanner host variable.
3. Ensure API and worker use the same durable shared object storage. Local filesystem storage is not suitable across separate hosts or replicas.
4. Apply PostgreSQL migrations and verify migration 0018 completed.
5. Upload the standard EICAR test file in a controlled non-production environment; verify it is rejected and never appears in the normal files list.
6. Verify a benign text/PDF/ZIP file moves through queued → checking → clean/released; verify PDF extraction status transitions pending → ready.
7. Stop ClamAV and verify uploads remain quarantined, retry, and ultimately show failed rather than clean.
8. Test oversized request bodies at the public ingress and under concurrent load.
9. Verify quarantine deletion, retention, backup/restore, object-store ACLs and worker recovery after forced termination.
10. Update the client to display inspection status before enabling the new upload contract for production users.

Do not run this worker on the public web service's shared host without a separate isolation review. Repository-level tests cannot certify the deployed host.
