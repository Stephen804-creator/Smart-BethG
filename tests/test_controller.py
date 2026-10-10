import shutil
import subprocess
import tempfile

import config
from controller import Controller
from tests.base import SmartBethGTestCase
from services.auth_service import create_user
from services.tool_service import resolve_workspace_root


class TestController(SmartBethGTestCase):
    def setUp(self):
        super().setUp()
        self._tmp = tempfile.mkdtemp(prefix="sbg_controller_projects_")
        self._orig_projects_dir = config.STORAGE_DIRS["projects"]
        config.STORAGE_DIRS["projects"] = self._tmp
        self.user = create_user("alice", "password123")
        self.controller = Controller()

    def tearDown(self):
        config.STORAGE_DIRS["projects"] = self._orig_projects_dir
        shutil.rmtree(self._tmp, ignore_errors=True)
        super().tearDown()

    def test_request_is_no_longer_stuck_queued_forever(self):
        """
        The core bug this closes: previously every request just became
        a "queued" task row that nothing ever updated again. Now the
        task's final status must reflect what actually happened.
        """
        result = self.controller.handle_request("hello there", user=self.user)
        self.assertNotEqual(result["status"], "queued")

        tasks = self.controller.task_service.list_tasks(self.user["id"])
        self.assertEqual(len(tasks), 1)
        self.assertNotEqual(tasks[0]["status"], "queued")

    def test_git_intent_updates_task_status_to_real_outcome(self):
        workspace_root = resolve_workspace_root("default")
        subprocess.run(["git", "init"], cwd=workspace_root, capture_output=True, check=True)

        result = self.controller.handle_request("git status", user=self.user, workspace="default")
        self.assertEqual(result["status"], "executed")

        tasks = self.controller.task_service.list_tasks(self.user["id"])
        self.assertEqual(tasks[0]["status"], "executed")

    def test_blank_request_rejected(self):
        with self.assertRaises(ValueError):
            self.controller.handle_request("   ", user=self.user)

    def test_tool_orchestrator_lists_tools(self):
        tools = self.controller.tool_orchestrator.list_tools()
        names = {t["name"] for t in tools}
        self.assertIn("git.read", names)
        self.assertIn("terminal.execute", names)
