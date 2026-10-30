# Units A–B — Execution Architecture and Quarantine Intake

Status: Unit A specifications added. Unit B quarantine intake foundation implemented; full secure-import acceptance is not yet complete.
Date: 2026-10-30

## Unit A — Architecture and security contract

Added:
- EXECUTION_PLATFORM_ARCHITECTURE.md — seven agreed backend responsibilities, trust zones, persistent-project versus temporary-compute lifecycle, runtime registry, isolation/network boundaries, storage and deployment shape.
- EXECUTION_THREAT_MODEL.md — assets, adversaries, trust boundaries, threat register, security invariants, host-dependent review and incident response.
- EXECUTION_SECURITY_REQUIREMENTS.md — normative requirements for upload/import, persistence, execution, supply chain, privacy, and verification.
- FILE_IMPORT_USER_EXPERIENCE.md — user journey, status language, recovery, privacy, and usability trade-offs; this is a product/engineering contract, not a UI implementation.

The architecture is modular responsibilities, not a demand for seven microservices. Rootless Docker, gVisor and Firecracker remain candidates pending inspection of the actual runner host. The UI is intentionally not implemented.

## Unit B — Implemented intake foundation

- Added PostgreSQL quarantine metadata migration 0017.
- Added a dedicated quarantine storage namespace, repository and service.
- New POST /api/v1/files uploads stream from UploadFile in bounded chunks and enter quarantine, not the ordinary files table.
- Added owner-scoped quarantine listing and deletion endpoints.
- Calculate SHA-256 and byte size server-side.
- Sanitize display filenames and derive media type from extension plus basic content signature/UTF-8 validation; client MIME type is recorded only as untrusted metadata.
- Reject unsupported extensions, empty files, invalid UTF-8 text, binary data presented as text, and obvious signature mismatches.
- ZIP files are held with archive_inspection_required. The API does not open or extract ZIP files.
- No scanner is configured, so accepted uploads remain quarantined. There is intentionally no user-facing release/accept endpoint. Quarantined content cannot enter the existing files/knowledge/execution path through the new upload route.

## Important limitations — do not call Unit B fully complete yet

1. Scanner integration and an operator-controlled release workflow are not implemented. Missing scanner must remain fail-closed.
2. ZIP central-directory inspection, traversal/link checks, archive-bomb limits, and safe extraction need an isolated inspection worker; they are not performed in the API process.
3. PDF/document parsing still exists in FileService and still runs in the application process for legacy records. Moving parsers to a restricted worker remains required.
4. Request-level body limiting is implemented on both upload aliases with bounded pre-buffering and two concurrent slots per process. The limit is per process, not global across replicas; production ingress must enforce a body cap too, and memory/load behavior needs deployment-level validation.
5. Existing file rows uploaded before this migration have not been retroactively moved or reclassified. Their status and handling need a deliberate compatibility migration and review.
6. No live object-storage durability, malware scanner, isolated archive worker, or production runner host was available for verification.

## Verification required before closing Unit B

- Run the full unit and PostgreSQL integration suites on this exact branch head.
- Add end-to-end multipart API tests for oversized bodies and quarantine ownership (middleware unit tests exist).
- Add scanner adapter and prove missing/error/timeout outcomes cannot release content.
- Add isolated archive inspection tests for traversal, links, duplicate paths, nested archives, entry count, expanded size, compression ratio, and time.
- Move PDF/document parsing out of the API process.
- Decide and test how legacy stored files are reclassified without deleting user data.
- Verify shared durable storage and restore behavior in the target deployment.

The upload path is a safe quarantine intake foundation, not a complete public file-import pipeline. It must not be described as malware-scanned or ready for extraction/execution until the remaining gates above pass. This branch is not a deployment authorization and does not certify Smart BethG for public file uploads or code execution.
