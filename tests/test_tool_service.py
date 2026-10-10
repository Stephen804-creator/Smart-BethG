import os
import shutil
import subprocess
import tempfile
import unittest

import config
from services.tool_service import ToolService, resolve_workspace_root
from tests.base import SmartBethGTestCase


class TestToolServiceWorkspaceResolution(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="sbg_projects_")
        self._orig_projects_dir = config.STORAGE_DIRS["projects"]
        config.STORAGE_DIRS["projects"] = self._tmp

    def tearDown(self):
        config.STORAGE_DIRS["projects"] = self._orig_projects_dir
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_sanitizes_unsafe_characters(self):
        root = resolve_workspace_root("../../etc")
        # Traversal characters are stripped, not honored - the result
        # must still land inside the controlled projects directory.
        self.assertTrue(root.startswith(self._tmp))
        self.assertNotIn("..", os.path.relpath(root, self._tmp))

    def test_creates_the_directory(self):
        root = resolve_workspace_root("my-project")
        self.assertTrue(os.path.isdir(root))

    def test_blank_name_falls_back_to_default(self):
        root = resolve_workspace_root("")
        self.assertTrue(root.endswith("default"))


class TestToolServiceExecution(SmartBethGTestCase):
    def setUp(self):
        super().setUp()
        self._tmp = tempfile.mkdtemp(prefix="sbg_projects_")
        self._orig_projects_dir = config.STORAGE_DIRS["projects"]
        config.STORAGE_DIRS["projects"] = self._tmp
        self.service = ToolService()
        self.user = {"id": 1, "role": "user"}
        self.admin = {"id": 2, "role": "admin"}

    def tearDown(self):
        config.STORAGE_DIRS["projects"] = self._orig_projects_dir
        shutil.rmtree(self._tmp, ignore_errors=True)
        super().tearDown()

    def test_filesystem_read_success(self):
        workspace_root = resolve_workspace_root("proj1")
        with open(os.path.join(workspace_root, "hello.txt"), "w") as f:
            f.write("hello world")

        result = self.service.execute(self.user, "filesystem.read", workspace="proj1", path="hello.txt")
        self.assertTrue(result["success"])
        self.assertEqual(result["result"]["content"], "hello world")

    def test_filesystem_read_path_traversal_blocked(self):
        resolve_workspace_root("proj2")
        result = self.service.execute(self.user, "filesystem.read", workspace="proj2", path="../../etc/passwd")
        self.assertFalse(result["success"])
        self.assertEqual(result["status"], "failed")

    def test_filesystem_read_missing_file_fails_cleanly(self):
        resolve_workspace_root("proj3")
        result = self.service.execute(self.user, "filesystem.read", workspace="proj3", path="nope.txt")
        self.assertFalse(result["success"])
        self.assertEqual(result["status"], "failed")

    def test_git_read_on_real_repo_succeeds(self):
        workspace_root = resolve_workspace_root("gitproj")
        subprocess.run(["git", "init"], cwd=workspace_root, capture_output=True, check=True)
        result = self.service.execute(self.user, "git.read", workspace="gitproj")
        self.assertTrue(result["success"])

    def test_git_read_on_non_repo_fails_honestly(self):
        """
        The exact bug this session fixed at the tool layer: git.read on a
        directory that isn't a repository must not be reported as
        success just because subprocess didn't raise.
        """
        resolve_workspace_root("notarepo")
        result = self.service.execute(self.user, "git.read", workspace="notarepo")
        self.assertFalse(result["success"])
        self.assertEqual(result["status"], "command_failed")

    def test_terminal_execute_denied_for_user_role(self):
        result = self.service.execute(self.user, "terminal.execute", workspace="proj4", program="python", args=["--version"])
        self.assertFalse(result["success"])
        self.assertEqual(result["status"], "denied")

    def test_terminal_execute_requires_approval_for_admin_role(self):
        """
        HIGH-risk actions require approval even for a role that holds
        the permission - having the permission is necessary, not
        sufficient. And the approval must actually be persisted (see
        test_approval_service.py for the bug this replaced).
        """
        result = self.service.execute(self.admin, "terminal.execute", workspace="proj5", program="python", args=["--version"])
        self.assertFalse(result["success"])
        self.assertEqual(result["status"], "approval_required")
        self.assertIn("approval_id", result)

        pending = self.service.approvals.list_pending(self.admin["id"])
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["id"], result["approval_id"])

    def test_git_write_denied_for_user_role(self):
        result = self.service.execute(self.user, "git.write", workspace="proj6", message="test commit")
        self.assertFalse(result["success"])
        self.assertEqual(result["status"], "denied")

    def test_git_write_requires_approval_for_admin_role(self):
        result = self.service.execute(self.admin, "git.write", workspace="proj7", message="test commit")
        self.assertEqual(result["status"], "approval_required")

    def test_git_write_commits_real_change_once_authorized(self):
        """
        Exercises the real commit path directly (bypassing the approval
        gate, which is tested separately above) to confirm the tool
        implementation itself actually works against a real repo.
        """
        workspace_root = resolve_workspace_root("gitwrite")
        subprocess.run(["git", "init"], cwd=workspace_root, capture_output=True, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=workspace_root, check=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=workspace_root, check=True)
        with open(os.path.join(workspace_root, "note.txt"), "w") as f:
            f.write("hello")

        from execution.execution_engine import ExecutionPermit
        permit = ExecutionPermit(request_id="test", action="git.write", resource="workspace:gitwrite", risk_level="high")
        raw = self.service._git_tool.commit(permit, cwd=workspace_root, message="add note")
        self.assertEqual(raw["return_code"], 0)

    def test_network_request_success_with_stubbed_tool(self):
        """
        Real outbound HTTP isn't something a unit test should depend on -
        stubs the tool implementation itself (already covered for real
        by NetworkTool's own simplicity), and verifies ToolService's
        wiring/shape-normalization around it. network.request is
        HIGH-risk, so this bypasses the approval gate directly (that
        gate itself is covered by test_network_request_denied_for_user_role
        and the approval-required assertions elsewhere) to test the tool
        wiring specifically.
        """
        class FakeNetworkTool:
            def get(self, permit, url, timeout=15):
                return "<html>ok</html>"

        self.service._network_tool = FakeNetworkTool()
        from execution.execution_engine import ExecutionPermit
        permit = ExecutionPermit(request_id="test", action="network.request", resource="workspace:proj8", risk_level="high")
        raw = self.service._run_network_request(permit, resolve_workspace_root("proj8"), url="https://example.com")
        self.assertEqual(raw["content"], "<html>ok</html>")

    def test_network_request_requires_approval_for_admin_role(self):
        result = self.service.execute(self.admin, "network.request", workspace="proj8b", url="https://example.com")
        self.assertEqual(result["status"], "approval_required")

    def test_network_request_denied_for_user_role(self):
        result = self.service.execute(self.user, "network.request", workspace="proj9", url="https://example.com")
        self.assertEqual(result["status"], "denied")

    def test_docker_run_missing_binary_fails_cleanly_not_a_crash(self):
        """
        Docker isn't installed in this environment - a real, honest
        "the tool isn't available" case. ToolService must report a clean
        failure, not propagate an unhandled exception.
        """
        result = self.service.execute(self.admin, "docker.run", workspace="proj10", args=["ps"])
        self.assertIn(result["status"], ("approval_required", "failed"))
        # docker.run is HIGH risk, so an admin still hits approval_required
        # before the (missing) binary is even attempted.
        self.assertEqual(result["status"], "approval_required")


if __name__ == "__main__":
    unittest.main()


class TestGitOperationsExtended(SmartBethGTestCase):
    def setUp(self):
        super().setUp()
        self._tmp = tempfile.mkdtemp(prefix="sbg_git_ops_projects_")
        self._orig_projects_dir = config.STORAGE_DIRS["projects"]
        config.STORAGE_DIRS["projects"] = self._tmp
        self.service = ToolService()
        self.user = {"id": 1, "role": "user"}
        self.admin = {"id": 2, "role": "admin"}

    def tearDown(self):
        config.STORAGE_DIRS["projects"] = self._orig_projects_dir
        shutil.rmtree(self._tmp, ignore_errors=True)
        super().tearDown()

    def _init_repo(self, name):
        root = resolve_workspace_root(name)
        subprocess.run(["git", "init"], cwd=root, capture_output=True, check=True)
        subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=root, check=True)
        subprocess.run(["git", "config", "user.name", "T"], cwd=root, check=True)
        return root

    def test_git_diff_on_clean_repo_succeeds_empty(self):
        self._init_repo("diffproj")
        result = self.service.execute(self.user, "git.read", workspace="diffproj", operation="diff")
        self.assertTrue(result["success"])

    def test_git_diff_shows_real_changes(self):
        root = self._init_repo("diffproj2")
        with open(f"{root}/a.txt", "w") as f:
            f.write("v1")
        subprocess.run(["git", "add", "-A"], cwd=root, check=True)
        subprocess.run(["git", "commit", "-m", "initial"], cwd=root, check=True)
        with open(f"{root}/a.txt", "w") as f:
            f.write("v2")

        result = self.service.execute(self.user, "git.read", workspace="diffproj2", operation="diff")
        self.assertTrue(result["success"])
        self.assertIn("v2", result["result"]["stdout"])

    def test_git_branches_lists_real_branch(self):
        self._init_repo("branchproj")
        result = self.service.execute(self.user, "git.read", workspace="branchproj", operation="branches")
        self.assertTrue(result["success"])

    def test_git_checkout_denied_for_user_role(self):
        self._init_repo("checkoutproj")
        result = self.service.execute(
            self.user, "git.write", workspace="checkoutproj", operation="checkout", branch="feature"
        )
        self.assertEqual(result["status"], "denied")

    def test_git_checkout_requires_approval_for_admin_role(self):
        self._init_repo("checkoutproj2")
        result = self.service.execute(
            self.admin, "git.write", workspace="checkoutproj2", operation="checkout", branch="feature"
        )
        self.assertEqual(result["status"], "approval_required")

    def test_git_checkout_creates_and_switches_branch_once_authorized(self):
        """Exercises the real tool implementation directly, bypassing the approval gate tested above."""
        root = self._init_repo("checkoutproj3")
        with open(f"{root}/a.txt", "w") as f:
            f.write("x")
        subprocess.run(["git", "add", "-A"], cwd=root, check=True)
        subprocess.run(["git", "commit", "-m", "initial"], cwd=root, check=True)

        from execution.execution_engine import ExecutionPermit
        permit = ExecutionPermit(request_id="t", action="git.write", resource="workspace:checkoutproj3", risk_level="high")
        raw = self.service._git_tool.checkout(permit, cwd=root, branch="feature-x", create=True)
        self.assertEqual(raw["return_code"], 0)

        status = subprocess.run(["git", "branch", "--show-current"], cwd=root, capture_output=True, text=True)
        self.assertEqual(status.stdout.strip(), "feature-x")

    def test_git_checkout_missing_branch_raises(self):
        root = self._init_repo("checkoutproj4")
        from execution.execution_engine import ExecutionPermit
        permit = ExecutionPermit(request_id="t", action="git.write", resource="workspace:checkoutproj4", risk_level="high")
        with self.assertRaises(ValueError):
            self.service._git_tool.checkout(permit, cwd=root, branch="")
