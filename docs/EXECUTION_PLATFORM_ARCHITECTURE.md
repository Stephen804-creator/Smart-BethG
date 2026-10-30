# Smart BethG Execution Platform Architecture

Status: implementation contract for Units A–I; not a production security certification.
Date: 2026-10-30

## Purpose and boundaries

The execution platform lets an authorized user work with persistent projects and explicitly request bounded processing or code execution. User work must persist independently of temporary compute. Submitted content must never inherit the privileges of the Smart BethG application.

This document governs backend execution. It does not prescribe the user interface, promise every language/runtime, or authorize arbitrary host, shell, network, provider, or connector access.

## Agreed backend responsibilities

These are separate responsibilities, not a requirement to deploy seven microservices:

1. **Agent orchestration:** interprets intent, plans work, selects approved capabilities, and requests operations. It does not execute untrusted code itself.
2. **Capability definitions:** versioned, platform-owned descriptions of supported operations, inputs, outputs, permissions, and limits. No third-party skills marketplace is required.
3. **Runtime registry:** operator-controlled inventory of approved runtime images, immutable digests, language/toolchain versions, approved commands, and resource profiles.
4. **Sandbox manager:** enforces isolation and creates, observes, cancels, and destroys execution environments.
5. **Permission and security layer:** authenticates users, checks ownership/workspace grants, validates capability permissions, applies quotas, and records security decisions.
6. **Execution workers:** consume durable jobs, run approved operations in isolated compute, and report bounded status/output.
7. **Artifact management:** stores outputs outside temporary compute with ownership, checksums, provenance, content metadata, versioning, safe retrieval, retention, and deletion.

Persistent project/file management is an essential supporting capability. It stores source files, uploads, snapshots, and user-approved changes independently of execution workers.

## Trust zones and data flow

- **User/API zone:** receives authenticated requests and validates request shape and size. Client MIME types, filenames, archive paths, source code, and metadata are untrusted.
- **Quarantine/inspection zone:** stores new uploads as untrusted, immutable input. Type checks and archive inspection run with strict resource limits. No automatic execution, API-process parsing, indexing, or model ingestion is permitted while quarantined.
- **Persistent project/storage zone:** holds accepted user files and versioned snapshots. Authorization is checked for every read, write, import, and export.
- **Control plane:** authorizes jobs and records durable job state. It sends typed job requests to a separately controlled execution manager; it never accepts arbitrary Docker commands, images, mounts, or environment variables from users or agents.
- **Execution zone:** a dedicated isolated worker/host runs approved runtime images and receives only the authorized snapshot and narrowly scoped inputs. It has no application/provider/database secrets, no Docker socket inside the job, and no default network egress.
- **Artifact zone:** receives bounded output through a controlled transfer path and stores it outside the ephemeral job environment.

Flow: authenticated upload → bounded quarantine write → type/signature and archive validation → inspection/scan decision → explicit acceptance/rejection → persistent project storage → authorized job request → permission/quota check → durable queue → isolated execution → bounded artifact transfer → artifact storage.

A file accepted for storage is not certified safe to execute. Execution remains a separate explicit permission and sandbox boundary.

## Persistent data versus temporary compute

Project files, uploads, saved edits, snapshots, and completed artifacts must survive job completion and worker replacement. Temporary containers/VMs may be destroyed after completion, timeout, cancellation, or policy violation. A later job restores only the selected authorized snapshot into a fresh environment.

An interactive session, if offered later, is a separate explicit mode with visible idle timeout, maximum lifetime, storage semantics, and recovery behavior.

## Execution lifecycle

Durable job states should distinguish accepted, queued, starting, running, cancelling, succeeded, failed, timed out, cancelled, rejected, and cleanup failed. Transitions must be validated and auditable. Repeated requests require idempotency. Worker leases/heartbeats and orphan recovery must prevent abandoned containers or permanently stuck jobs.

Each job is bound to an immutable project snapshot, runtime digest, capability version, user identity, authorization decision, resource profile, and bounded output/artifact budget.

## Runtime registry

Only operator-reviewed runtimes may be scheduled. Each entry records runtime ID, language/toolchain version, immutable image digest, approved commands, supported capability IDs, resource/security profile, provenance/SBOM references, scan status, and enabled state.

User uploads, project Dockerfiles, package manifests, or agent-generated build instructions must never become trusted runtime images automatically. Runtime expansion is incremental; Python support does not imply every language is available.

## Isolation and network policy

Default deny. No host filesystem mounts beyond narrowly scoped read-only input and explicit output channels; no host PID/network namespaces, devices, privileged mode, Docker socket, or application secrets. Apply CPU, memory, PID, wall-clock, disk, file-count, open-file, output, concurrency, and per-user quotas.

Network is disabled by default. If package installation is later supported, route it through a controlled egress service or curated mirror with destination allowlists, DNS/IP validation, private/metadata address blocking, bandwidth/time limits, and audit. Do not grant general internet access for convenience.

A budget tier may lower resource ceilings or concurrency. It must never weaken the platform's minimum security profile.

## Storage and deployment

Quarantine, persistent project storage, temporary worker scratch, and artifacts are distinct logical areas. Every object is owner-scoped and uses opaque identifiers, checksums, size limits, server-detected content types, and retention metadata. Downloads default to attachment disposition and nosniff. Untrusted HTML/SVG/script content must not execute in the application origin.

Local filesystem storage is for development/single-instance use. Multi-instance production requires shared durable object storage and separately verified backup/restore.

Start with a modular codebase and explicit boundaries. Deploy API/control plane and execution workers separately where the host/security boundary requires it. The execution manager and container runtime belong on a hardened runner host/VM, not inside the public web process trust boundary. Do not split every responsibility into a microservice without measured need.

Rootless Docker, gVisor, and Firecracker remain candidate technologies, not decisions made here. Select only after reviewing the actual host, kernel, workload, operational capability, and adversarial evidence.

## Deferred and excluded

- No skills marketplace or third-party downloadable capability definitions.
- No arbitrary host terminal, host filesystem, or unrestricted network automation.
- No user-controlled runtime image or automatic Dockerfile promotion.
- No claim that malware scanning proves code safe.
- No isolation technology selected before host evaluation.
- No UI implementation; UI/UX follows the user's separate design.
- No production-host certification from source tests alone.
