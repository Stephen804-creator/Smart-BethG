import unittest
from unittest.mock import patch

from docker.docker_tool import DockerTool
from execution.execution_engine import ExecutionPermit


class TestDockerTool(unittest.TestCase):
    def setUp(self):
        self.permit = ExecutionPermit("request-1", "docker.run", "workspace:default", "high")

    @patch("docker.docker_tool.subprocess.run")
    def test_constrained_allowlisted_run_is_passed_as_argv(self, run):
        run.return_value = type("Completed", (), {"returncode": 0, "stdout": "ok", "stderr": ""})()
        tool = DockerTool(allowed_images=["alpine:3.20"])
        args = [
            "run", "--rm", "--network=none", "--read-only", "--cap-drop=ALL",
            "--security-opt=no-new-privileges", "--memory=512m", "--cpus=1",
            "--pids-limit=128", "--user=10001:10001", "--tmpfs",
            "/tmp:rw,noexec,nosuid,size=64m", "alpine:3.20", "echo", "hello world",
        ]
        result = tool.run(self.permit, args)
        self.assertEqual(result.returncode, 0)
        run.assert_called_once()
        self.assertEqual(run.call_args.args[0][-2:], ["echo", "hello world"])

    def test_container_execution_requires_allowlisted_image(self):
        tool = DockerTool(allowed_images=[])
        with self.assertRaises(PermissionError):
            tool.run(self.permit, ["run", "alpine:latest", "echo", "hi"])

    def test_privileged_and_host_mount_options_are_rejected(self):
        tool = DockerTool(allowed_images=["alpine:3.20"])
        with self.assertRaises(PermissionError):
            tool.run(self.permit, ["run", "--privileged", "alpine:3.20", "id"])
        with self.assertRaises(PermissionError):
            tool.run(self.permit, ["run", "-v", "/:/host", "alpine:3.20", "id"])

    def test_read_only_inspection_command_is_allowed(self):
        tool = DockerTool()
        with patch("docker.docker_tool.subprocess.run") as run:
            run.return_value = type("Completed", (), {"returncode": 0, "stdout": "", "stderr": ""})()
            tool.run(self.permit, ["ps", "--all"])
            run.assert_called_once()


if __name__ == "__main__":
    unittest.main()
