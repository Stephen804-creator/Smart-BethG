# Smart BethG isolated execution images

This directory contains the application-owned image definitions for the runtime IDs in `services/runtime_registry.py`. Each image runs as UID/GID 65534, has no custom entrypoint, and is invoked only through the fixed command in the runtime registry. The API accepts a runtime ID and source text; callers cannot select images, commands, environment variables or entrypoints.

## Runtime image inventory

| Runtime ID | Dockerfile | Toolchain |
|---|---|---|
| python | python/Dockerfile | CPython 3.12 |
| javascript | javascript/Dockerfile | Node.js 24 |
| typescript | typescript/Dockerfile | Node.js 24 type stripping; not a static type-checker |
| java | java/Dockerfile | Eclipse Temurin JDK 21 source launcher |
| c | c/Dockerfile | GCC 14 / C17 |
| cpp | cpp/Dockerfile | GCC 14 / C++20 |
| go | go/Dockerfile | Go 1.27.3 |
| rust | rust/Dockerfile | Rust stable toolchain |
| csharp | csharp/Dockerfile | .NET 10 SDK file-based app |
| php | php/Dockerfile | PHP CLI 8.4 |
| dart | dart/Dockerfile | Dart stable SDK |
| kotlin | kotlin/Dockerfile | Kotlin compiler 2.4.21, SHA-256 verified at build |
| swift | swift/Dockerfile | Swift 6.4 |
| bash | bash/Dockerfile | Debian Bash 5.2 package |
| powershell | powershell/Dockerfile | PowerShell 7.6 bundled with .NET SDK 10 |
| ruby | ruby/Dockerfile | Ruby 3.4 |
| elixir | elixir/Dockerfile | Elixir 1.20.5 / OTP from official image |
| r | r/Dockerfile | R 4.6.1 |
| julia | julia/Dockerfile | Julia 1.13.3 |
| lua | lua/Dockerfile | Lua 5.4 |
| perl | perl/Dockerfile | Perl 5.42 |

The upstream base-image tags are versioned but may move as publishers refresh their tags. The CI pipeline always builds with `--pull`, tests the resulting image, and—when publishing is explicitly requested—records the immutable registry digest. Do not treat a mutable base tag as an immutable deployment reference.

## Build and verification

The GitHub Actions workflow `.github/workflows/runtime-images.yml` builds each image independently, reports CRITICAL/HIGH findings through Trivy (report-only; review is still required), and executes a smoke program through the same `SandboxService._docker_run_command` used by the application. The check exercises the fixed runtime invocation, non-root UID, network isolation, read-only root filesystem, bounded resources (including per-language compiler artifact file-size caps), and container cleanup.

The workflow runs on pushes and pull requests that change the runtime images or execution code. It does not publish images during ordinary CI.

After this workflow is merged into the repository's default branch, manually run **Smart BethG isolated runtime images** from the intended branch and explicitly set `publish_images=true`. GitHub only accepts manual dispatch for workflows present on the default branch. Publishing is a separate job requiring `packages: write`; it rebuilds the tested images with BuildKit SBOM and provenance attestations, pushes commit-specific tags to GHCR, pulls each resulting digest, runs the same smoke test against that exact digest, and writes the digest references to the workflow summary.

## Enabling a runtime

A runtime remains disabled until its exact published digest is configured by an operator. For each runtime:

1. Copy the immutable `ghcr.io/stephen804-creator/smart-bethg-runtime-<id>@sha256:<digest>` reference from the successful workflow summary.
2. Add that exact reference to `SMART_BETHG_DOCKER_ALLOWED_IMAGES`.
3. Set the corresponding `SMART_BETHG_SANDBOX_<RUNTIME>_IMAGE` environment variable to the same reference.
4. Confirm that the production runner is rootless and run the execution and cleanup regression suite against that host.
5. Enable the global sandbox flag only after host-level review and approval.

Do not enable every runtime merely because its image built. Review its SBOM, provenance, transitive licenses, vulnerabilities, update cadence, and runtime-specific behavior. Compiler images are substantially larger and need resource limits appropriate to the workload. The application currently exposes conservative per-runtime limits.

## Boundaries

- The smoke tests prove a minimal single-file program can run. They do not establish full project builds, framework/package-manager support, multi-file workspaces, dependency installation, or artifact export.
- The container has no network. External package installation is intentionally unavailable during user execution.
- SQL is not an executable image in this group; it requires a separate disposable-database runner with no production credentials.
- Hardware flashing, serial ports, SWD/JTAG, and USB access require a separate authenticated local-device agent.
- Swift execution here is a Linux Swift script profile. Apple SDK, iOS/macOS app packaging, Xcode, and signing require a separately governed macOS runner.
- MATLAB remains a licensing-review item and is not bundled.
- Image publication is not production enablement. Operators must approve the digests and verify the actual rootless Docker host.
