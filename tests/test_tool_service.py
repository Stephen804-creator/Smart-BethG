import os
import tempfile
import unittest
from unittest.mock import patch

import config
from services.tool_service import (
    DIRECT_EXECUTION_DISABLED_REASON,
    ToolService,
    normalize_workspace_name,
    resolve_workspace_root,
)


class TestWorkspaceLabels(unittest.TestCase):
    def test_workspace_name_is_canonicalized(self):
        self.assertEqual(normalize_workspace_name("../../my project"), "myproject")
        self.assertEqual(normalize_workspace_name(""), "default")

    def test_workspace_paths_are_user_scoped_and_not_created(self):
        with tempfile.TemporaryDirectory() as root:
            with patch.dict(config.STORAGE_DIRS, {"projects": root}):
                one = resolve_workspace_root(1, "default")
                two = resolve_workspace_root(2, "default")
                self.assertNotEqual(one, two)
                self.assertTrue(one.startswith(os.path.join(root, "1")))
                self.assertFalse(os.path.exists(one))


class TestDirectExecutionDisabled(unittest.TestCase):
    def test_every_direct_action_fails_closed_without_side_effects(self):
        service = ToolService(approval_service=object(), audit_service=object())
        for action in (
            "filesystem.read", "filesystem.write", "git.read", "git.write",
            "terminal.execute", "network.request", "docker.run",
        ):
            with self.subTest(action=action):
                result = service.execute(
                    {"id": 42, "role": "admin"}, action,
                    workspace="default", program="python", args=["-c", "raise SystemExit(1)"],
                )
                self.assertFalse(result["success"])
                self.assertEqual(result["status"], "unavailable")
                self.assertTrue(result["connector_required"])
                self.assertIn("connector", result["reason"].lower())

    def test_reason_is_explicit(self):
        self.assertIn("disabled", DIRECT_EXECUTION_DISABLED_REASON.lower())


if __name__ == "__main__":
    unittest.main()
