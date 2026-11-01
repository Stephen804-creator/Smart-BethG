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
from services.sandbox_service import SandboxService, SandboxUnavailableError


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
            resolve_runtime("fortran")
        with self.assertRaises(RuntimeUnavailableError):
            resolve_runtime("javascript")

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

    def test_registry_does_not_expose_private_runtime_configuration(self):
        with patch.dict(os.environ, {"SMART_BETHG_SANDBOX_ENABLED": "false"}):
            runtimes = list_runtimes()
        self.assertEqual(runtimes[0]["id"], "python")
        for runtime in runtimes:
            with self.subTest(runtime_id=runtime["id"]):
                self.assertFalse(runtime["enabled"])
                for private_field in (
                    "image", "image_env", "environment", "executable", "arguments"
                ):
                    self.assertNotIn(private_field, runtime)


    def test_core_language_profiles_are_registered_but_disabled_without_approved_images(self):
        from services.runtime_registry import RUNTIME_DEFINITIONS

        expected = {
            "python", "javascript", "typescript", "java", "c", "cpp", "go",
            "rust", "php", "csharp", "dart", "kotlin", "swift", "bash", "powershell",
            "ruby", "elixir", "r", "julia", "lua", "perl",
        }
        self.assertTrue(expected.issubset(RUNTIME_DEFINITIONS))
        env = {
            "SMART_BETHG_SANDBOX_ENABLED": "true",
            "SMART_BETHG_SANDBOX_PYTHON_IMAGE": self.image,
        }
        for runtime in RUNTIME_DEFINITIONS.values():
            if runtime.runtime_id != "python":
                env[runtime.image_env] = ""
        with patch.dict(os.environ, env), patch.object(
            config, "DOCKER_ALLOWED_IMAGES", {self.image}
        ):
            listed = {item["id"]: item for item in list_runtimes()}
            for runtime_id in expected - {"python"}:
                with self.subTest(runtime_id=runtime_id):
                    self.assertFalse(listed[runtime_id]["enabled"])
                    with self.assertRaises(RuntimeUnavailableError):
                        resolve_runtime(runtime_id)

    def test_compiled_runtime_uses_only_fixed_command_and_read_only_source_path(self):
        from services.runtime_registry import RUNTIME_DEFINITIONS

        runtime = RUNTIME_DEFINITIONS["c"]
        with tempfile.TemporaryDirectory() as directory:
            command = SandboxService._docker_run_command(
                "/usr/bin/docker", "sbx-test", Path(directory),
                "approved@sha256:" + ("e" * 64), runtime,
            )
        self.assertIn('cc -std=c17 -O2 -pipe -o /runner/smartbethg-program "$1" && /runner/smartbethg-program', command)
        self.assertEqual(command[-1], "/workspace/main.c")
        self.assertEqual(command[command.index("approved@sha256:" + ("e" * 64)) + 1], "/bin/sh")
        runner_mount = command[command.index("--tmpfs", command.index("--tmpfs") + 1) + 1]
        self.assertTrue(runner_mount.startswith("/runner:rw,exec,nosuid,nodev,size="))
        self.assertNotIn("noexec", runner_mount)
        self.assertNotIn("--privileged", command)

    def test_runtime_environment_is_application_controlled(self):
        from services.runtime_registry import RUNTIME_DEFINITIONS

        runtime = RUNTIME_DEFINITIONS["go"]
        with tempfile.TemporaryDirectory() as directory:
            command = SandboxService._docker_run_command(
                "/usr/bin/docker", "sbx-test", Path(directory),
                "approved@sha256:" + ("f" * 64), runtime,
            )
        self.assertIn("GOTOOLCHAIN=local", command)
        self.assertIn("GOPROXY=off", command)
        self.assertIn("--network=none", command)

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

    def test_dotnet_runtime_gets_a_bounded_higher_open_file_limit(self):
        from services.runtime_registry import RUNTIME_DEFINITIONS

        runtime = RUNTIME_DEFINITIONS["csharp"]
        with tempfile.TemporaryDirectory() as directory:
            command = SandboxService._docker_run_command(
                "/usr/bin/docker", "sbx-test", Path(directory),
                "approved@sha256:" + ("8" * 64), runtime,
            )
        self.assertIn("nofile=256:256", command)
        self.assertNotIn("nofile=unlimited", command)
        self.assertIn("DOTNET_SKIP_FIRST_TIME_EXPERIENCE=1", command)
        self.assertIn("DOTNET_CLI_TELEMETRY_OPTOUT=1", command)

    def test_docker_command_does_not_accept_caller_controlled_command_or_image(self):
        runtime = resolve_runtime_for_test()
        with tempfile.TemporaryDirectory() as directory:
            command = SandboxService._docker_run_command(
                "/usr/bin/docker", "sbx-test", Path(directory),
                "approved@sha256:" + ("c" * 64), runtime,
            )
        self.assertEqual(command[-4:], ["python", "-I", "-B", "/workspace/main.py"])
        self.assertEqual(command[-5], "approved@sha256:" + ("c" * 64))

    def test_execution_error_fails_closed_when_cleanup_cannot_be_verified(self):
        runtime = resolve_runtime_for_test()
        image = "approved@sha256:" + ("d" * 64)
        with patch("services.sandbox_service.resolve_runtime", return_value=(runtime, image)), \
             patch("services.sandbox_service.shutil.which", return_value="/usr/bin/docker"), \
             patch("services.sandbox_service.subprocess.Popen", side_effect=OSError("docker run failed")), \
             patch.object(SandboxService, "_cleanup_container", return_value=False), \
             patch.object(SandboxService, "_record") as record, \
             patch.object(config, "IS_PRODUCTION", False):
            with self.assertRaisesRegex(SandboxUnavailableError, "could not be confirmed removed"):
                SandboxService().execute_runtime(7, "python", "print('safe')")

        self.assertEqual(record.call_args.args[-1], "sandbox_cleanup_unverified")

    def test_cleanup_attempts_force_remove_even_when_kill_fails(self):
        missing = SimpleNamespace(returncode=1, stdout="", stderr="Error: No such object: sbx-test")
        with patch("services.sandbox_service.subprocess.run", side_effect=[
            OSError("docker kill failed"),
            SimpleNamespace(returncode=0, stdout="", stderr=""),
            missing,
        ]) as run:
            self.assertTrue(SandboxService._cleanup_container("/usr/bin/docker", "sbx-test"))
        commands = [call.args[0] for call in run.call_args_list]
        self.assertEqual(commands[0][1], "kill")
        self.assertEqual(commands[1][1:3], ["rm", "--force"])
        self.assertEqual(commands[2][1], "inspect")

    def test_cleanup_fails_closed_when_daemon_cannot_confirm_absence(self):
        unavailable = SimpleNamespace(
            returncode=1, stdout="", stderr="Cannot connect to the Docker daemon"
        )
        with patch("services.sandbox_service.subprocess.run", return_value=unavailable):
            self.assertFalse(SandboxService._cleanup_container("/usr/bin/docker", "sbx-test"))

    def test_container_absence_verification_retries_cleanup_for_existing_container(self):
        present = SimpleNamespace(returncode=0, stdout="[]", stderr="")
        with patch("services.sandbox_service.subprocess.run", return_value=present), patch.object(
            SandboxService, "_cleanup_container", return_value=True
        ) as cleanup:
            self.assertTrue(SandboxService._ensure_container_absent("/usr/bin/docker", "sbx-test"))
        cleanup.assert_called_once_with("/usr/bin/docker", "sbx-test")

    def test_container_absence_verification_rejects_ambiguous_inspect_failure(self):
        unavailable = SimpleNamespace(
            returncode=1, stdout="", stderr="Cannot connect to the Docker daemon"
        )
        with patch("services.sandbox_service.subprocess.run", return_value=unavailable):
            self.assertFalse(SandboxService._ensure_container_absent("/usr/bin/docker", "sbx-test"))

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
