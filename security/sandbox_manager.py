"""Smart BethG execution-isolation contract.

LV: A directory is NOT a real sandbox. Real isolation must eventually be
provided by a hardened container, VM, or dedicated job runner. This module
only defines scope and path validation.
"""
from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True)
class SandboxSpec:
    workspace: Path
    network_enabled: bool = False
    max_seconds: int = 60
    max_memory_mb: int = 512
    read_only_root: bool = True

class SandboxManager:
    def create_spec(self, workspace):
        return SandboxSpec(Path(workspace).resolve())

    def validate_path(self, spec, target):
        candidate = Path(target).resolve()
        try:
            candidate.relative_to(spec.workspace)
        except ValueError as exc:
            raise PermissionError("Path is outside the assigned workspace.") from exc
        return candidate
