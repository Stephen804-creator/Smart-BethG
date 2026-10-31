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


## Unified software and hardware engineering capability catalog

The C-D branch also adds `services/engineering_capability_registry.py` and an authenticated `GET /api/v1/sandbox/capabilities` endpoint. This is the shared capability catalog for the future Engineering Lab. It deliberately separates:

- Languages and language runtimes (Python, JavaScript, TypeScript, Java, C/C++, Go, Rust, PHP, C#, Dart).
- Runtime/compiler/SDK toolchains (Node.js, JVM, GCC/Clang, Go, Rust, .NET, Flutter, Android and Apple toolchains).
- Framework/build profiles (React, Angular, Vue, Next.js, Vite, Express, NestJS, FastAPI, Django, Flask, Spring Boot, ASP.NET Core, Laravel, Flutter, React Native, Unity, Unreal and Godot). Frameworks are not programming languages or independent runtimes.
- Embedded toolchains and runtimes (Arduino CLI, ESP-IDF, PlatformIO, MicroPython and CircuitPython).
- Hardware-description languages (Verilog, VHDL and SystemVerilog).
- Hardware targets (Arduino Uno, ESP32, RP2040/Pico, STM32 and FPGA families).
- Engineering tools (Wokwi, KiCad, EasyEDA, ngspice and Renode).
- Execution profiles (managed cloud sandbox, external connector and a future local agent).

The catalog also defines three workspace modes: Software Engineering, Hardware Engineering, and Software + Hardware. The latter two are roadmap states, not existing working interfaces. Software + Hardware is intended to link related project context while retaining distinct hardware/software views and histories.

**Important availability rule:** only Python is an implemented language runtime in this increment, and it is still disabled unless the operator enables the feature and supplies an exact digest-pinned allowlisted image. All other languages/toolchains remain planned. Wokwi, KiCad and EasyEDA are integration candidates, not connected tools. Hardware targets are catalog entries, not devices that Smart BethG can currently flash or control. The catalog endpoint never exposes private image references, secrets or host paths. Entries also reserve fields for supported file formats, host requirements and license-review status so a future connector/runtime cannot be treated as approved merely because its name is listed.

This avoids confusing a language with its compiler, a framework with a runtime, a board with a language, or an external application with an installed integration. A future runtime can be selected only through its reviewed stable ID and operator-controlled profile. A future connector or local agent must separately declare permissions, supported actions, formats, target compatibility, execution location and license constraints.

Simulation results must always be labeled as simulated. They do not prove physical circuit safety, correct wiring, electrical ratings or reliable operation on a real board. Physical USB/serial/flash access requires an explicit, user-approved local agent with device-level permissions; it must never be inferred from a cloud runtime.

## Compatibility and operational boundaries

- Existing Python endpoint and owner-scoped run history remain available.
- The code does not add Node, Java, C/C++, Go, Rust, PHP, .NET, Dart, Bash, or PowerShell images. Those runtimes must not appear as enabled until individually reviewed and registered.
- Rootless Docker is a required production precondition for this in-process Docker runner. If the host cannot provide rootless Docker, keep sandbox execution disabled; do not weaken the requirement merely to make deployment pass.
- Docker's default seccomp/AppArmor behavior and host kernel configuration remain host-dependent. Verify them on the actual runner. This PR does not claim that source tests prove kernel isolation.
- The API still starts Docker directly and performs execution synchronously. Dedicated execution manager/worker isolation, durable queueing, global concurrency, per-user quotas, project snapshot integration, and artifact transfer remain in later units.
- Do not enable the feature in production until a reviewed runtime image is built, pinned, allowlisted, and tested on the actual rootless runner with adversarial workloads.
