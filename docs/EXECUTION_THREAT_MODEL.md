# Smart BethG Execution Platform Threat Model

Status: initial threat model for Units A–I. Review whenever trust boundaries or runtime behavior change.
Date: 2026-10-30

## Assets

User credentials, sessions, provider/connector credentials, PostgreSQL data, ownership boundaries, project files, uploads, source code, private artifacts, API/control-plane availability, worker capacity, host kernel, container daemon, runner host, object storage, runtime images, job state, and artifact provenance.

## Adversaries and failure sources

Assume a public authenticated user can submit hostile source code, malformed documents, crafted ZIP archives, misleading filenames/MIME types, huge files, path traversal entries, symlinks, decompression bombs, process floods, output floods, and concurrent requests. Also consider compromised accounts, malicious dependencies, vulnerable parsers, compromised runtime images, compromised API processes, worker crashes, storage/network failures, and operator misconfiguration. Benign mistakes can trigger the same resource exhaustion.

## Trust boundaries

1. Browser/client to API.
2. API to quarantine/object storage and PostgreSQL.
3. Quarantine/inspection process to accepted persistent project storage.
4. API/control plane to execution manager/queue.
5. Execution manager to host kernel/container/VM isolation.
6. Untrusted job to output/artifact transfer.
7. Application services to external package registries/providers/connectors.

The execution host is a separate trust zone. A job must not reach the host daemon, host filesystem, metadata endpoints, internal services, database, provider APIs, or other tenants' data.

## Threat register

| Threat | Required controls | Evidence |
|---|---|---|
| Oversized request exhausts API memory | Streaming byte limit, request-body limit, user/concurrency quotas | Chunked upload tests at and above limit |
| MIME/extension spoofing | Server signature detection and explicit type policy | Mismatch/polyglot corpus |
| Malicious document parser | Quarantine; parser in isolated worker with resource limits | Hostile document corpus |
| ZIP path traversal | Canonical path validation; reject absolute paths, traversal, links, special files, collisions | Crafted archive suite |
| Decompression/archive bomb | Entry, expanded-byte, compression-ratio, nesting and time limits | High-ratio/many-entry tests |
| Malware or malicious dependency | Quarantine and scanner policy; no automatic execution | Scanner unavailable/error behavior |
| Cross-user access | Owner/workspace checks on every operation | Cross-tenant service/API tests |
| Sandbox escape | Dedicated runner, least privilege, namespaces, seccomp/LSM, no socket/secrets/network | Adversarial tests on production host |
| Daemon compromise via API | Separate execution manager/runner boundary | Host/deployment review |
| Resource exhaustion | CPU/memory/PID/time/disk/file/output/concurrency quotas | Parallel load and exhaustion tests |
| Output XSS or data leakage | Bounded output, escaped text, attachment downloads, safe logs | Browser/content and log tests |
| Orphaned execution | Durable state, leases, verified cleanup, orphan sweeper | Worker crash/recovery tests |
| Runtime supply-chain compromise | Immutable digest, reviewed build, SBOM, vulnerability scan, provenance | Image attestations |
| Network exfiltration/SSRF | Default-deny egress, controlled proxy, private/metadata IP blocking | DNS rebinding and egress tests |
| Storage loss/tampering | Checksums, durable storage, backup/restore | Restore drill |

## Security invariants

- Uploading a file never executes it.
- Quarantined content is not indexed, summarized, parsed in the API process, or used as agent context.
- Client content type is advisory only.
- Missing scanner, scanner error, timeout, or indeterminate result never becomes clean.
- A stored project file is not automatically executable.
- A scan pass does not bypass sandbox isolation or authorization.
- Jobs receive only the selected authorized snapshot and minimum inputs.
- No untrusted job receives runtime control, application secrets, or unrestricted network.
- Resource limits are enforced outside the submitted process.
- User work and artifacts persist independently of temporary compute.
- Security decisions are attributable without logging private file contents.

## Host-dependent questions

Before enabling production execution, inspect the actual runner host: daemon rootless/rootful mode, socket permissions, kernel/namespaces, seccomp, AppArmor/SELinux, cgroups, storage mounts, network routes, metadata-service reachability, and monitoring. Source code cannot prove these properties.

## Incident response

On suspected escape/host compromise: stop scheduling, isolate the runner from application/data networks, revoke runner credentials, preserve minimal forensic metadata, rebuild from a reviewed image, rotate exposed credentials, and assess project/artifact integrity. A container restart alone is not sufficient remediation for suspected host compromise.
