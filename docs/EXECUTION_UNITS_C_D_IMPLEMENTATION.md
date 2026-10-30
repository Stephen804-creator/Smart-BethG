# Execution platform Units C–D

Status: implementation branch only. This document is not a production-host security certification.

## Unit C — Runtime registry

- Adds an application-owned, version-controlled runtime registry. User requests select a stable runtime ID, never a Docker image, shell command, entrypoint, mount, or environment.
- Python is the only registered runtime in this first increment. The registry is structured so another language can be added only after its toolchain, exact image digest, fixed invocation, dependencies, resource profile, and security tests are reviewed.
- A runtime is enabled only when the feature switch is on, its image is pinned to a complete lowercase SHA-256 digest, and the exact image reference is in the operator allowlist.
- Adds authenticated `GET /api/v1/sandbox/runtimes`, `POST /api/v1/sandbox/execute`, and preserves `POST /api/v1/sandbox/python` for compatibility.
- The runtime listing deliberately omits private image references and configuration names.

## Unit D — Sandbox isolation hardening

The Docker invocation is fixed in application code and adds:
- No network, private IPC, read-only root filesystem, read-only source mount, non-root UID, all Linux capabilities dropped, and no-new-privileges.
- No image pulls at execution time; only the exact local digest-pinned and allowlisted image can run.
- CPU, memory, memory-plus-swap, process, shared-memory, temporary-filesystem, file-size, open-file, wall-clock, and combined output limits.
- No Docker log driver storage for user output; output is captured through the bounded attached streams.
- A production preflight that fails closed unless Docker reports rootless mode.
- Container cleanup after timeout, output-limit termination, normal completion, or execution errors; the daemon is queried to verify the named container is absent. Failure to confirm removal fails the run.

## Compatibility and operational boundaries

- Existing Python endpoint and owner-scoped run history remain available.
- The code does not add Node, Java, C/C++, Go, Rust, PHP, .NET, Dart, Bash, or PowerShell images. Those runtimes must not appear as enabled until individually reviewed and registered.
- Rootless Docker is a required production precondition for this in-process Docker runner. If the host cannot provide rootless Docker, keep sandbox execution disabled; do not weaken the requirement merely to make deployment pass.
- Docker's default seccomp/AppArmor behavior and host kernel configuration remain host-dependent. Verify them on the actual runner. This PR does not claim that source tests prove kernel isolation.
- The API still starts Docker directly and performs execution synchronously. Dedicated execution manager/worker isolation, durable queueing, global concurrency, per-user quotas, project snapshot integration, and artifact transfer remain in later units.
- Do not enable the feature in production until a reviewed runtime image is built, pinned, allowlisted, and tested on the actual rootless runner with adversarial workloads.
