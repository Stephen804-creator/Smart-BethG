# Units A–B — Execution Architecture and Quarantine Intake

Status: Unit A specifications and Unit B asynchronous quarantine/inspection code implemented; deployment and host-isolation acceptance remain gated.
Date: 2026-10-30

## Unit A — Architecture and security contract

Added:
- EXECUTION_PLATFORM_ARCHITECTURE.md — seven agreed backend responsibilities, trust zones, persistent-project versus temporary-compute lifecycle, runtime registry, isolation/network boundaries, storage and deployment shape.
- EXECUTION_THREAT_MODEL.md — assets, adversaries, trust boundaries, threat register, security invariants, host-dependent review and incident response.
- EXECUTION_SECURITY_REQUIREMENTS.md — normative requirements for upload/import, persistence, execution, supply chain, privacy, and verification.
- FILE_IMPORT_USER_EXPERIENCE.md — user journey, status language, recovery, privacy, and usability trade-offs; this is a product/engineering contract, not a UI implementation.

The architecture is modular responsibilities, not a demand for seven microservices. Rootless Docker, gVisor and Firecracker remain candidates pending inspection of the actual runner host. The UI is intentionally not implemented.

## Unit B — Implemented intake and inspection pipeline

- Added PostgreSQL quarantine metadata migration 0017.
- Added a dedicated quarantine storage namespace, repository and service.
- New POST /api/v1/files uploads are read in bounded chunks and enter quarantine, not the ordinary files table.
- The quarantine row and a durable `file.inspect` job are committed in one PostgreSQL transaction. The existing worker now claims inspection jobs alongside mission/workflow jobs.
- The worker verifies the stored SHA-256, sends content to a ClamAV daemon using the bounded INSTREAM protocol, and releases only a clean file. Scanner absence, timeout, malformed response, or indeterminate result retries and eventually leaves the file failed/quarantined.
- Clean release copies the opaque object to the trusted uploads namespace and creates the ordinary file row plus released quarantine state in one database transaction. No user-facing release endpoint exists.
- ZIP metadata is inspected without extraction; traversal/absolute/drive paths, symlinks, duplicate paths, encrypted entries, nested archives, excessive entry counts, expanded size, and suspicious compression ratios are rejected. The original ZIP may be released as a file but is never automatically extracted.
- User status includes the separate inspection state (queued/checking/clean/rejected/failed); rejected content remains private in quarantine until the user deletes it or an operator applies a reviewed retention action.
- Added owner-scoped quarantine listing and deletion endpoints.
- Calculate SHA-256 and byte size server-side.
- Sanitize display filenames and derive media type from extension plus basic content signature/UTF-8 validation; client MIME type is recorded only as untrusted metadata.
- Reject unsupported extensions, empty files, invalid UTF-8 text, binary data presented as text, and obvious signature mismatches.
- ZIP files are held with archive_inspection_required. The API does not open or extract ZIP files.
- No scanner is configured, so accepted uploads remain quarantined. There is intentionally no user-facing release/accept endpoint. Quarantined content cannot enter the existing files/knowledge/execution path through the new upload route.

## Compatibility and user-impact warning

- Existing file records and their existing read/download/extract behavior are not migrated by this change.
- New uploads are returned as quarantine records, not ordinary file records. They do not appear in the normal `/files` list and cannot yet be passed to existing file-id extraction/summary/knowledge endpoints.
- This is an intentional security boundary but a breaking upload-response/workflow change for any client that assumes upload immediately returns a usable file ID. No UI/client migration is included here.
- Do not merge/deploy this upload-route behavior until the scanner/release pipeline and client status/ready workflow are implemented and tested together. The live deployment has not been changed.

## Remaining acceptance gates

1. Configure and deploy a private ClamAV daemon and a separately deployed inspection worker. The repository contains the client and durable worker handler, but the actual scanner host/service is not provisioned or verified here.
2. The inspection worker must run in a restricted container/host with no public ingress, no Docker socket, no unrelated application/provider secrets, strict CPU/memory/PID/disk limits, and private-only scanner/storage/database access. Code separation alone does not prove host isolation.
3. ZIP metadata inspection is implemented without extraction. If archive extraction is later enabled, it must be a separate isolated operation with additional nested-depth, actual decompressed-byte, path/link and timeout enforcement.
4. PDF/document parsing for legacy trusted file records still exists in FileService and has not yet been migrated to the isolated worker. New uploads are malware-scanned before release, but PDF parser isolation remains a release blocker for production-grade file processing.
5. Request-level body limiting is implemented on both upload aliases with bounded pre-buffering and two concurrent slots per process. The limit is per process, not global across replicas; production ingress must enforce a body cap too, and memory/load behavior needs deployment-level validation.
6. Existing file rows uploaded before this migration have not been retroactively moved or reclassified. Their status and handling need a deliberate compatibility migration and review.
7. No live object-storage durability, malware scanner, isolated worker host, or production runner host was available for verification.

## Verification required before closing Unit B

- Run the full unit and PostgreSQL integration suites on this exact branch head.
- Add end-to-end multipart API tests for oversized bodies and quarantine ownership (middleware unit tests exist).
- Add scanner adapter and prove missing/error/timeout outcomes cannot release content.
- Add isolated archive inspection tests for traversal, links, duplicate paths, nested archives, entry count, expanded size, compression ratio, and time.
- Move PDF/document parsing out of the API process.
- Decide and test how legacy stored files are reclassified without deleting user data.
- Verify shared durable storage and restore behavior in the target deployment.

The upload path is a safe quarantine intake foundation, not a complete public file-import pipeline. It must not be described as malware-scanned or ready for extraction/execution until the remaining gates above pass. This branch is not a deployment authorization and does not certify Smart BethG for public file uploads or code execution.
