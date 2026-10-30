# Smart BethG Execution Security Requirements

Status: normative baseline for execution-platform implementation.
Date: 2026-10-30

The words MUST, MUST NOT, SHOULD, and MAY express engineering requirements.

## Upload and import

- API MUST enforce streaming request-body and per-user/concurrency limits.
- Service MUST generate object identifiers; filenames are display metadata only.
- Service MUST calculate SHA-256 and byte length server-side.
- Client MIME type MUST NOT determine trust or parser selection.
- New content MUST enter quarantine and remain unavailable for extraction, indexing, summarization, execution, or agent context until an explicit acceptance decision.
- Type validation MUST combine normalized extension policy with server-side signature detection. Unknown, mismatched, malformed, or unsupported types MUST be rejected or remain quarantined; never mark them clean.
- Archive inspection MUST reject absolute paths, drive prefixes, traversal, symlinks/hardlinks, special files, duplicate/colliding normalized paths, excessive entries/nesting, oversized expanded content, and suspicious compression ratios.
- Extraction MUST run in a resource-limited isolated process, never in the API request process.
- Scanner absence, failure, timeout, or indeterminate result MUST fail closed. A scanner pass is not proof of safe execution.
- Uploading MUST NOT automatically execute, build, install, or run project content.

## Persistence and access

- Quarantine, project files, worker scratch, and artifacts MUST be separate logical areas.
- Every read/write/delete/release operation MUST enforce owner/workspace authorization.
- User project data MUST survive worker/container destruction.
- Multi-instance production MUST use shared durable storage and verified restore.
- Downloads MUST default to attachment and nosniff; active content MUST NOT execute in the app origin.
- Stored objects MUST carry checksums, detected media type, size, state, owner, timestamps, and provenance.

## Execution

- Only operator-approved immutable runtime digests and capability versions may be scheduled.
- Job authorization MUST be checked at enqueue and immediately before execution.
- Execution manager MUST be outside the public web process trust boundary and accept typed job requests, not arbitrary daemon commands.
- Job MUST receive only a specific authorized project snapshot and approved inputs.
- Default network policy is deny-all. Egress exceptions MUST be explicit, destination-constrained, logged, and tested.
- Job MUST NOT receive application/provider/database credentials, host paths, privileged devices, host namespaces, or runtime sockets.
- Enforce CPU, memory, PID, wall-clock, disk, file-count, open-file, output, concurrency, and per-user quotas externally.
- Cancellation/timeout MUST terminate the process/container, verify cleanup, and record cleanup failures.
- Output MUST be bounded while being read; crossing aggregate limit MUST stop the job, not merely truncate retained text.
- Durable job states, leases, idempotency, retries, and orphan cleanup MUST handle worker crashes and ambiguous outcomes.

## Runtime and supply chain

- Runtime definitions are platform-controlled and versioned.
- Runtime images MUST be pinned by digest; provenance, SBOM, vulnerability status, and rebuild policy SHOULD be retained.
- User Dockerfiles/dependency declarations MUST NOT automatically modify the trusted runtime registry.
- Package installation, if enabled, MUST use controlled egress and dependency policy.

## Observability and privacy

- Record job/user IDs, runtime digest, capability version, resource profile, state transitions, timestamps, exit status, resource usage, and cleanup result.
- Do not log raw source, project contents, secrets, cookies, provider credentials, or unbounded stdout/stderr.
- Logs/artifacts MUST be owner-authorized and retained/deleted by documented policy.
- High-impact account restrictions require deterministic evidence and human review; anomaly signals alone MUST NOT permanently suspend an account.

## Verification gates

No production execution enablement until exact-release CI passes; upload/archive adversarial tests pass; scanner failure cases fail closed; parser worker resource limits are demonstrated; production runner host configuration is reviewed; sandbox escape/network/filesystem/metadata/socket/process/output/disk/concurrency tests pass on that host; cleanup/orphan recovery is tested; durable project/artifact backup and restore are demonstrated; and independent security review accepts residual risks.

Repository tests alone cannot satisfy host-specific gates.
