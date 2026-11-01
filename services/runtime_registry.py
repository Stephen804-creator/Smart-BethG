"""Operator-controlled registry of executable language runtimes.

Only definitions shipped with the application can be selected. Runtime images
come from operator configuration and must be digest-pinned and allowlisted.
User input can select a runtime ID, never an image, command, or entrypoint.
"""
from dataclasses import dataclass
import os
import re

import config


class RuntimeUnavailableError(RuntimeError):
    """Raised when a runtime is unknown, disabled, or not safely configured."""


@dataclass(frozen=True)
class RuntimeDefinition:
    runtime_id: str
    language: str
    display_name: str
    version_label: str
    image_env: str
    executable: str
    arguments: tuple[str, ...]
    source_filename: str
    command_name: str
    environment: tuple[str, ...] = ()
    max_source_bytes: int = 64_000
    timeout_seconds: int = 15
    memory_limit: str = "256m"
    cpu_limit: str = "0.50"
    pids_limit: int = 64
    tmpfs_size: str = "16m"

    def public_dict(self, enabled: bool) -> dict:
        return {
            "id": self.runtime_id,
            "language": self.language,
            "name": self.display_name,
            "version": self.version_label,
            "enabled": enabled,
            "max_source_bytes": self.max_source_bytes,
            "timeout_seconds": self.timeout_seconds,
        }


# Every entry below is an application-owned, fixed invocation. It is not
# enabled merely by being listed: an operator must build/review its image,
# pin the immutable SHA-256 digest, add that exact reference to the allowlist,
# and verify it on the dedicated rootless runner. No user-supplied image,
# Dockerfile, command, shell fragment, dependency manifest, or entrypoint is
# accepted by this registry.
#
# Compiler runners use a fixed, application-authored shell command. The only
# variable passed to that command is the path of the read-only source file.
RUNTIME_DEFINITIONS = {
    "python": RuntimeDefinition(
        runtime_id="python", language="python", display_name="Python",
        version_label="operator-pinned image",
        image_env="SMART_BETHG_SANDBOX_PYTHON_IMAGE",
        executable="python", arguments=("-I", "-B"),
        source_filename="main.py", command_name="python_script",
    ),
    "javascript": RuntimeDefinition(
        runtime_id="javascript", language="javascript", display_name="JavaScript",
        version_label="operator-pinned Node.js image",
        image_env="SMART_BETHG_SANDBOX_NODE_IMAGE",
        executable="node", arguments=("--disable-proto=throw",),
        source_filename="main.js", command_name="javascript_script",
    ),
    "typescript": RuntimeDefinition(
        runtime_id="typescript", language="typescript", display_name="TypeScript",
        version_label="Node.js type-stripping image; no static type-check",
        image_env="SMART_BETHG_SANDBOX_TYPESCRIPT_IMAGE",
        executable="node", arguments=("--experimental-strip-types", "--disable-proto=throw"),
        source_filename="main.ts", command_name="typescript_script",
    ),
    "java": RuntimeDefinition(
        runtime_id="java", language="java", display_name="Java",
        version_label="operator-pinned JDK source-launcher image",
        image_env="SMART_BETHG_SANDBOX_JAVA_IMAGE",
        executable="java", arguments=(),
        source_filename="Main.java", command_name="java_source",
        environment=("HOME=/dev/shm", "TMPDIR=/dev/shm"),
        timeout_seconds=20, memory_limit="384m",
    ),
    "c": RuntimeDefinition(
        runtime_id="c", language="c", display_name="C",
        version_label="operator-pinned C compiler image",
        image_env="SMART_BETHG_SANDBOX_C_IMAGE",
        executable="/bin/sh",
        arguments=("-c", "cc -std=c17 -O2 -pipe -o /dev/shm/smartbethg-program \"$1\" && /dev/shm/smartbethg-program", "smartbethg-c"),
        source_filename="main.c", command_name="c_compile_and_run",
        timeout_seconds=20, memory_limit="384m",
    ),
    "cpp": RuntimeDefinition(
        runtime_id="cpp", language="cpp", display_name="C++",
        version_label="operator-pinned C++ compiler image",
        image_env="SMART_BETHG_SANDBOX_CPP_IMAGE",
        executable="/bin/sh",
        arguments=("-c", "c++ -std=c++20 -O2 -pipe -o /dev/shm/smartbethg-program \"$1\" && /dev/shm/smartbethg-program", "smartbethg-cpp"),
        source_filename="main.cpp", command_name="cpp_compile_and_run",
        timeout_seconds=20, memory_limit="384m",
    ),
    "go": RuntimeDefinition(
        runtime_id="go", language="go", display_name="Go",
        version_label="operator-pinned Go toolchain image",
        image_env="SMART_BETHG_SANDBOX_GO_IMAGE",
        executable="go", arguments=("run",),
        source_filename="main.go", command_name="go_run",
        environment=(
            "HOME=/dev/shm", "GOCACHE=/dev/shm/go-cache",
            "GOTMPDIR=/dev/shm", "GOTOOLCHAIN=local",
            "GOPROXY=off", "GOSUMDB=off",
        ),
        timeout_seconds=25, memory_limit="512m",
    ),
    "rust": RuntimeDefinition(
        runtime_id="rust", language="rust", display_name="Rust",
        version_label="operator-pinned Rust compiler image",
        image_env="SMART_BETHG_SANDBOX_RUST_IMAGE",
        executable="/bin/sh",
        arguments=("-c", "rustc --edition=2024 -C debuginfo=0 -o /dev/shm/smartbethg-program \"$1\" && /dev/shm/smartbethg-program", "smartbethg-rust"),
        source_filename="main.rs", command_name="rust_compile_and_run",
        environment=("HOME=/dev/shm", "TMPDIR=/dev/shm"),
        timeout_seconds=25, memory_limit="512m",
    ),
    "php": RuntimeDefinition(
        runtime_id="php", language="php", display_name="PHP",
        version_label="operator-pinned PHP CLI image",
        image_env="SMART_BETHG_SANDBOX_PHP_IMAGE",
        executable="php",
        arguments=("-n", "-d", "allow_url_fopen=0", "-d", "display_errors=stderr"),
        source_filename="main.php", command_name="php_script",
    ),
    "dart": RuntimeDefinition(
        runtime_id="dart", language="dart", display_name="Dart",
        version_label="operator-pinned Dart SDK image",
        image_env="SMART_BETHG_SANDBOX_DART_IMAGE",
        executable="dart", arguments=(),
        source_filename="main.dart", command_name="dart_script",
        environment=("HOME=/dev/shm", "PUB_CACHE=/dev/shm/pub-cache"),
        timeout_seconds=25, memory_limit="384m",
    ),
    "kotlin": RuntimeDefinition(
        runtime_id="kotlin", language="kotlin", display_name="Kotlin",
        version_label="operator-pinned Kotlin/JVM compiler image",
        image_env="SMART_BETHG_SANDBOX_KOTLIN_IMAGE",
        executable="kotlinc", arguments=("-script",),
        source_filename="main.kts", command_name="kotlin_script",
        environment=("HOME=/dev/shm", "TMPDIR=/dev/shm"),
        timeout_seconds=25, memory_limit="512m",
    ),
    "swift": RuntimeDefinition(
        runtime_id="swift", language="swift", display_name="Swift",
        version_label="operator-pinned Swift toolchain image",
        image_env="SMART_BETHG_SANDBOX_SWIFT_IMAGE",
        executable="swift", arguments=(),
        source_filename="main.swift", command_name="swift_script",
        environment=("HOME=/dev/shm", "TMPDIR=/dev/shm"),
        timeout_seconds=25, memory_limit="512m",
    ),
    "bash": RuntimeDefinition(
        runtime_id="bash", language="bash", display_name="Bash",
        version_label="operator-pinned Bash image",
        image_env="SMART_BETHG_SANDBOX_BASH_IMAGE",
        executable="bash", arguments=("--noprofile", "--norc"),
        source_filename="main.sh", command_name="bash_script",
    ),
    "powershell": RuntimeDefinition(
        runtime_id="powershell", language="powershell", display_name="PowerShell",
        version_label="operator-pinned PowerShell image",
        image_env="SMART_BETHG_SANDBOX_POWERSHELL_IMAGE",
        executable="pwsh",
        arguments=("-NoLogo", "-NoProfile", "-NonInteractive", "-File"),
        source_filename="main.ps1", command_name="powershell_script",
        environment=("HOME=/dev/shm", "TMPDIR=/dev/shm"),
        timeout_seconds=20, memory_limit="384m",
    ),
}


def is_digest_pinned_image(image: str) -> bool:
    return bool(re.fullmatch(r"[^@\\s]+@sha256:[0-9a-f]{64}", image or ""))


def resolve_runtime(runtime_id: str) -> tuple[RuntimeDefinition, str]:
    """Resolve an enabled runtime and its exact operator-approved image."""
    runtime = RUNTIME_DEFINITIONS.get(runtime_id)
    if runtime is None:
        raise RuntimeUnavailableError("The requested runtime is not registered.")
    image = os.getenv(runtime.image_env, "").strip()
    if (
        os.getenv("SMART_BETHG_SANDBOX_ENABLED", "false").strip().lower() != "true"
        or not is_digest_pinned_image(image)
        or image not in config.DOCKER_ALLOWED_IMAGES
    ):
        raise RuntimeUnavailableError(
            f"{runtime.display_name} execution is not enabled or its image is not approved."
        )
    return runtime, image


def list_runtimes() -> list[dict]:
    """Return registry metadata without exposing private image references."""
    result = []
    for runtime in RUNTIME_DEFINITIONS.values():
        try:
            resolve_runtime(runtime.runtime_id)
            enabled = True
        except RuntimeUnavailableError:
            enabled = False
        result.append(runtime.public_dict(enabled))
    return result
