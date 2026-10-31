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


# Add a language here only after its image, command, dependencies, resource
# profile, provenance, and adversarial tests have been reviewed. No user-
# supplied Dockerfile or image can add a runtime.
RUNTIME_DEFINITIONS = {
    "python": RuntimeDefinition(
        runtime_id="python",
        language="python",
        display_name="Python",
        version_label="operator-pinned image",
        image_env="SMART_BETHG_SANDBOX_PYTHON_IMAGE",
        executable="python",
        arguments=("-I", "-B"),
        source_filename="main.py",
        command_name="python_script",
    ),
}


def is_digest_pinned_image(image: str) -> bool:
    return bool(re.fullmatch(r"[^@\s]+@sha256:[0-9a-f]{64}", image or ""))


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
