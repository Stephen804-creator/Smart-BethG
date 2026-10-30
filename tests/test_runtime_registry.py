"""Unit and security regression tests for the runtime registry and Docker policy."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import config
from services.runtime_registry import (
    RuntimeUnavailableError,
    is_digest_pinned_image,
    list_runtimes,
    resolve_runtime,
)
from services.sandbox_service import SandboxService


class TestRuntimeRegistry(unittest.TestCase):
    def setUp(self):
        self.image = "registry.example/smartbethg-python@sha256:" + ("a" * 64)

    def test_only_operator_registered_runtime_is_available(self):
        with patch.dict(os.environ, {
            "SMART_BETHG_SANDBOX_ENABLED": "true",
            "SMART_BETHG_SANDBOX_PYTHON_IMAGE": self.image,
        }), patch.object(config, "DOCKER_ALLOWED_IMAGES", {self.image}):
            runtime, image = resolve_runtime("python")
        self.assertEqual(runtime.runtime_id, "python")
        self.assertEqual(image, self.image)
        with self.assertRaises(RuntimeUnavailableError):
            resolve_runtime("bash")
        with self.assertRaises(RuntimeUnavailableError):
            resolve_runtime("node")

    def test_runtime_is_disabled_without_exact_digest_allowlist(self):
        with patch.dict(os.environ, {
            "SMART_BETHG_SANDBOX_ENABLED": "true",
            "SMART_BETHG_SANDBOX_PYTHON_IMAGE": self.image,
        }), patch.object(config, "DOCKER_ALLOWED_IMAGES", set()):
            with self.assertRaises(RuntimeUnavailableError):
                resolve_runtime("python")

    def test_runtime_is_disabled_when_feature_flag_is_off(self):
        with patch.dict(os.environ, {
            "SMART_BETHG_SANDBOX_ENABLED": "false",
            "SMART_BETHG_SANDBOX_PYTHON_IMAGE": self.image,
        }), patch.object(config, "DOCKER_ALLOWED_IMAGES", {self.image}):
            with self.assertRaises(RuntimeUnavailableError):
                resolve_runtime("python")

    def test_registry_does_not_expose_image_reference(self):
        with patch.dict(os.environ, {"SMART_BETHG_SANDBOX_ENABLED": "false"}):
            runtime = list_runtimes()[0]
        self.assertEqual(runtime["id"], "python")
        self.assertFalse(runtime["enabled"])
        self.assertNotIn("image", runtime)
        self.assertNotIn("image_env", runtime)

    def test_digest_validation_rejects_tags_and_malformed_digests(self):
        self.assertTrue(is_digest_pinned_image(self.image))
        self.assertFalse(is_digest_pinned_image("python:latest"))
        self.assertFalse(is_digest_pinned_image("python@sha256:abc"))
        self.assertFalse(is_digest_pinned_image("python@sha256:" + ("A" * 64)))


class TestSandboxIsolationPolicy(unittest.TestCase):
    def test_docker_command_has_required_isolation_and_resource_limits(self):
        runtime = resolve_runtime_for_test()
        with tempfile.TemporaryDirectory() as directory:
            command = SandboxService._docker_run_command(
                "/usr/bin/docker", "sbx-test", Path(directory),
                "registry.example/python@sha256:" + ("b" * 64), runtime,
            )
        joined = " ".join(command)
        required = [
            "--pull=never", "--network=none", "--ipc=private", "--read-only",
            "--cap-drop=ALL", "--security-opt=no-new-privileges:true",
            "--pids-limit 64", "--memory 256m", "--memory-swap 256m",
            "--cpus 0.50", "--shm-size=16m", "--ulimit nofile=64:64",
            "--ulimit fsize=1048576:1048576", "--ulimit core=0:0",
            "--log-driver=none", "--user=65534:65534",
            "noexec,nosuid,nodev", "readonly",
        ]
        for item in required:
            self.assertIn(item, joined)
        self.assertNotIn("--privileged", command)
        self.assertNotIn("--network=host", command)
        self.assertNotIn("/var/run/docker.sock", joined)

    def test_docker_command_does_not_accept_caller_controlled_command_or_image(self):
        runtime = resolve_runtime_for_test()
        with tempfile.TemporaryDirectory() as directory:
            command = SandboxService._docker_run_command(
                "/usr/bin/docker", "sbx-test", Path(directory),
                "approved@sha256:" + ("c" * 64), runtime,
            )
        self.assertEqual(command[-4:], ["python", "-I", "-B", "/workspace/main.py"])
        self.assertEqual(command[-5], "approved@sha256:" + ("c" * 64))

    def test_rootless_detection_fails_closed_on_command_error(self):
        with patch("services.sandbox_service.subprocess.run", return_value=SimpleNamespace(
            returncode=1, stdout="", stderr="unavailable"
        )):
            self.assertFalse(SandboxService._docker_is_rootless("/usr/bin/docker"))

    def test_rootless_detection_requires_explicit_rootless_security_option(self):
        with patch("services.sandbox_service.subprocess.run", return_value=SimpleNamespace(
            returncode=0, stdout=json.dumps(["name=seccomp,profile=builtin"]), stderr=""
        )):
            self.assertFalse(SandboxService._docker_is_rootless("/usr/bin/docker"))
        with patch("services.sandbox_service.subprocess.run", return_value=SimpleNamespace(
            returncode=0, stdout=json.dumps(["name=seccomp,profile=builtin", "name=rootless"]), stderr=""
        )):
            self.assertTrue(SandboxService._docker_is_rootless("/usr/bin/docker"))


def resolve_runtime_for_test():
    from services.runtime_registry import RUNTIME_DEFINITIONS
    return RUNTIME_DEFINITIONS["python"]


if __name__ == "__main__":
    unittest.main()
