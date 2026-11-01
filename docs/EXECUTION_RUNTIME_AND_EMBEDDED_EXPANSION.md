# Execution runtime and embedded toolchain expansion

Status: registry and catalog code added on a follow-up branch stacked on PR #27. This is not a runtime-image release, production enablement, or hardware integration.

## Language runtime profiles

The runtime registry now contains fixed application-owned profiles for:

| Family | Registered profile IDs | Invocation model |
|---|---|---|
| Existing baseline | `python` | Isolated Python script |
| Web/server | `javascript`, `typescript` | Node.js script; TypeScript uses Node's type-stripping mode and does not perform static type checking |
| JVM / .NET | `java`, `kotlin`, `csharp` | Java source launcher, Kotlin script compiler, .NET 10 file-based C# app |
| Native / systems | `c`, `cpp`, `go`, `rust` | Fixed compile-and-run or Go single-file invocation |
| General scripting | `php`, `dart`, `bash`, `powershell` | Fixed interpreter invocation |
| Extended scripting / data | `ruby`, `elixir`, `r`, `julia`, `lua`, `perl` | Fixed interpreter invocation |

The new definitions are not automatically enabled. Each runtime has its own operator image environment variable. A runtime resolves only when the global sandbox switch is enabled, the configured image has a complete lowercase SHA-256 digest, and that exact image reference is in the operator allowlist. The registry API continues to hide image references and internal environment variable names.

The runtime command, source filename, resource profile and static environment are application-owned. Client requests still provide only a stable runtime ID and source text. Compiler profiles use fixed commands; no caller-provided shell command or Docker image is accepted. C/C++, Go, Rust, C#, and Swift use a separate size-bounded executable scratch tmpfs; the general `/tmp` mount remains `noexec`. Go is configured to use local toolchain/cache paths and offline module resolution.

### Important limits

- The branch adds registry definitions and safe command construction, not prebuilt OCI images. No new language is enabled until its image has been built from reviewed inputs, pinned, allowlisted, scanned, tested and verified on the dedicated rootless runner.
- Node.js TypeScript type stripping is not a substitute for a TypeScript project type-check/build pipeline.
- Single-file execution is not full project support. Multi-file projects, dependency installation, framework builds, package managers, test profiles and generated artifacts need the language-neutral project snapshot/job/artifact contract in Unit E.
- C#, Java, Kotlin, Swift, Go, Rust, compilers and interpreters must be validated with their actual pinned images. A registered invocation is not proof that a compatible image exists or that its runtime works in production.
- HTML/CSS remain web preview/build formats, not standalone code runtimes.
- SQL is intentionally not connected to any Smart BethG database. It needs a disposable, isolated database capability with explicit schema/data seeding and no production credentials.
- MATLAB remains excluded from bundled runtime plans until its licensing and redistribution rights are explicitly cleared. Apple-platform builds require a compatible macOS runner and licensing review.

## Additional catalog-only language families

The catalog also records the remaining roadmap candidates without claiming that they have runnable images: SQL, PL/pgSQL, T-SQL, PL/SQL, Objective-C, Zig, Assembly, GDScript, MATLAB, Mojo and Gleam. Their execution models are different:

- SQL dialects require disposable database instances and must never receive production Smart BethG credentials or tenant data.
- Objective-C Apple-platform builds require compatible Apple SDK hosts.
- Assembly requires an architecture-specific constrained emulator.
- GDScript requires a Godot project and engine profile.
- MATLAB remains subject to license and redistribution review.
- Zig, Mojo and Gleam require separately pinned compiler/runtime images and compatibility tests.

HTML/CSS remain web preview/build formats rather than general-purpose runtimes. Frameworks such as Rails remain project/build profiles, not additional programming languages. These entries are planned catalog metadata only.

## Embedded and Arduino engineering catalog expansion

The shared engineering catalog now includes additional hardware targets and toolchain/tool entries:

- Arduino families: Mega 2560, Nano and Uno R4, in addition to the existing Uno.
- Espressif: ESP32-C3 and ESP32-S3 variants, in addition to the existing ESP32 family.
- Raspberry Pi: Pico W, in addition to RP2040/Pico.
- ST: STM32 Nucleo boards, in addition to the STM32 family.
- Toolchains and board support: Arduino board cores and AVR-GCC.
- Programming/debugging utilities: AVRDUDE, esptool and OpenOCD.
- Firmware framework: Zephyr RTOS.
- Digital design tools: Icarus Verilog, GHDL and Yosys.

These are catalog entries only. They do not install or connect the tools, flash a board, open a serial port, simulate a circuit, or synthesize/program an FPGA. Board revisions, MCU variants, bootloaders, SDK versions, licensing, and host requirements must be resolved in explicit project/build profiles.

Arduino CLI and PlatformIO are project-oriented: a real build depends on a project layout, board environment and package/toolchain selection. ESP-IDF likewise requires an ESP-IDF project and its configured toolchain. They must not be represented as working single-file runtimes merely because the tool names are present. See the official [PlatformIO project build workflow](https://docs.platformio.org/en/latest/core/quickstart.html) and [ESP-IDF tooling documentation](https://docs.espressif.com/projects/idf-im-ui/en/latest/cli_commands.html).

Physical USB, serial, SWD/JTAG and flashing access requires a separately authenticated, user-approved local agent or dedicated device runner. Cloud execution must not claim access to a user's attached board. Simulator output must be labelled as simulated and is not proof of electrical safety or physical hardware correctness.

## Enablement checklist for each runtime/toolchain

1. Build a dedicated image from a trusted source with an explicit version and license review.
2. Generate and record the immutable image digest and provenance.
3. Review the fixed executable, arguments, environment, source filename and resource limits.
4. Run functional and adversarial tests, including filesystem, network, process, output and timeout cases.
5. Scan the image and its dependencies; document update ownership and rollback.
6. Add the exact digest to operator allowlisting and configure the corresponding environment variable.
7. Verify execution, cleanup, resource enforcement and cross-user isolation on the actual rootless runner.
8. Only then enable the runtime and advertise it as executable.

Unit E must add project-aware snapshots and capability-aware runner scheduling before Smart BethG claims full application builds, multi-file Arduino/ESP-IDF/PlatformIO projects, dependency resolution, artifact export or physical-device access.
