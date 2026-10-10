"""Restricted Docker integration.

The Docker daemon is a host-level security boundary. This wrapper deliberately
rejects arbitrary Docker CLI passthrough, host mounts, host networking, device
access, privileged mode, and Docker context/host overrides.
"""
import re
import subprocess

import config
from execution.execution_engine import ExecutionPermit


READ_ONLY_COMMANDS = {"ps", "images", "version", "info", "inspect", "logs"}
REQUIRED_RUN_FLAGS = {
    "--rm",
    "--network=none",
    "--read-only",
    "--cap-drop=ALL",
    "--security-opt=no-new-privileges",
    "--memory=512m",
    "--cpus=1",
    "--pids-limit=128",
    "--user=10001:10001",
    "--tmpfs",
    "/tmp:rw,noexec,nosuid,size=64m",
}
FORBIDDEN_FLAGS = (
    "--privileged", "--volume", "-v", "--mount", "--device", "--network=host",
    "--pid=host", "--ipc=host", "--uts=host", "--cap-add", "--security-opt=apparmor=unconfined",
    "--env-file", "-e", "--publish", "-p", "--add-host", "--runtime", "--gpus",
    "--context", "--host", "-H",
)


class DockerTool:
    def __init__(self, allowed_images=None):
        self.allowed_images = set(
            allowed_images if allowed_images is not None else config.DOCKER_ALLOWED_IMAGES
        )

    def run(self, permit: ExecutionPermit, args, cwd=None):
        if permit.action != "docker.run":
            raise PermissionError("Invalid permit.")
        if not isinstance(args, list) or not args or any(not isinstance(x, str) for x in args):
            raise TypeError("Docker args must be a non-empty list of strings.")
        if any(flag == arg or arg.startswith(flag + "=") for arg in args for flag in FORBIDDEN_FLAGS):
            raise PermissionError("This Docker option is blocked by Smart BethG's security policy.")

        command = args[0]
        if command in READ_ONLY_COMMANDS:
            if any(arg.startswith("--context") or arg.startswith("--host") for arg in args):
                raise PermissionError("Changing the Docker context or daemon host is blocked.")
            return subprocess.run(
                ["docker", *args], cwd=cwd, capture_output=True, text=True,
                timeout=30, check=False,
            )

        if command != "run":
            raise PermissionError(
                "Only read-only Docker inspection commands and constrained 'docker run' are allowed."
            )
        if not self.allowed_images:
            raise PermissionError(
                "Container execution is disabled until an operator configures SMART_BETHG_DOCKER_ALLOWED_IMAGES."
            )
        if not REQUIRED_RUN_FLAGS.issubset(set(args)):
            raise PermissionError(
                "docker run must use the required no-network, read-only, non-root, resource-limited profile."
            )

        # Parse the allowlisted image after required options; reject every
        # unrecognized option before the image so mounts/privilege flags cannot
        # be smuggled in. Only --tmpfs is allowed to take a separate value.
        i = 1
        while i < len(args):
            token = args[i]
            if token == "--tmpfs":
                if i + 1 >= len(args) or args[i + 1] != "/tmp:rw,noexec,nosuid,size=64m":
                    raise PermissionError("Only the bounded, no-exec /tmp tmpfs is allowed.")
                i += 2
                continue
            if token in REQUIRED_RUN_FLAGS:
                i += 1
                continue
            if token.startswith("-"):
                raise PermissionError(f"Docker option is not allowlisted: {token}")
            image = token
            command_args = args[i + 1:]
            break
        else:
            raise ValueError("docker run requires an allowlisted image.")

        if image not in self.allowed_images:
            raise PermissionError("Container image is not in SMART_BETHG_DOCKER_ALLOWED_IMAGES.")
        if not command_args:
            raise ValueError("A command must be provided for the allowlisted container image.")
        if any(not item or len(item) > 1024 or any(ord(ch) < 32 for ch in item) for item in command_args):
            raise ValueError("Container command arguments are empty, too long, or contain control characters.")

        return subprocess.run(
            ["docker", *args], cwd=cwd, capture_output=True, text=True,
            timeout=60, check=False,
        )
