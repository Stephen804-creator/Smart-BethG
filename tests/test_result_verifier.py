import unittest

from agent.result_verifier import verify_result


class TestResultVerifier(unittest.TestCase):
    def test_command_success(self):
        result = verify_result("terminal.execute", {"return_code": 0, "stdout": "ok", "stderr": ""})
        self.assertTrue(result["success"])
        self.assertEqual(result["status"], "executed")

    def test_command_nonzero_exit_is_not_success(self):
        """
        This is the exact anti-pattern the verifier exists to catch: the
        tool "ran" without raising, but it failed. A non-zero exit code
        must never be reported as success.
        """
        result = verify_result("terminal.execute", {"return_code": 1, "stdout": "", "stderr": "boom"})
        self.assertFalse(result["success"])
        self.assertEqual(result["status"], "command_failed")
        self.assertIn("boom", result["reason"])

    def test_command_unexpected_shape_is_unverifiable(self):
        result = verify_result("terminal.execute", "not a dict")
        self.assertFalse(result["success"])
        self.assertEqual(result["status"], "unverifiable")

    def test_git_read_uses_command_verification(self):
        ok = verify_result("git.read", {"return_code": 0, "stdout": "", "stderr": ""})
        self.assertTrue(ok["success"])
        failed = verify_result("git.read", {"return_code": 128, "stdout": "", "stderr": "fatal: not a git repository"})
        self.assertFalse(failed["success"])

    def test_git_write_uses_command_verification(self):
        ok = verify_result("git.write", {"return_code": 0, "stdout": "1 file changed", "stderr": ""})
        self.assertTrue(ok["success"])
        failed = verify_result("git.write", {"return_code": 1, "stdout": "", "stderr": "nothing to commit"})
        self.assertFalse(failed["success"])

    def test_docker_run_uses_command_verification(self):
        ok = verify_result("docker.run", {"return_code": 0, "stdout": "", "stderr": ""})
        self.assertTrue(ok["success"])
        failed = verify_result("docker.run", {"return_code": 125, "stdout": "", "stderr": "invalid reference"})
        self.assertFalse(failed["success"])

    def test_network_request_requires_content_key(self):
        ok = verify_result("network.request", {"content": "<html>hi</html>", "url": "https://example.com"})
        self.assertTrue(ok["success"])
        bad = verify_result("network.request", {"url": "https://example.com"})
        self.assertFalse(bad["success"])

    def test_filesystem_read_requires_content_key(self):
        ok = verify_result("filesystem.read", {"content": "hello", "path": "a.txt"})
        self.assertTrue(ok["success"])
        bad = verify_result("filesystem.read", {"path": "a.txt"})
        self.assertFalse(bad["success"])

    def test_unknown_action_fails_closed(self):
        result = verify_result("something.imaginary", {"whatever": True})
        self.assertFalse(result["success"])
        self.assertEqual(result["status"], "unverifiable")


if __name__ == "__main__":
    unittest.main()
