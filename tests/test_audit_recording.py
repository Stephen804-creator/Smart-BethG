import shutil
import tempfile

import config
from tests.base import SmartBethGTestCase
from services.auth_service import create_user
from services.tool_service import ToolService
from services.audit_service import AuditService


class TestAuditRecording(SmartBethGTestCase):
    """
    Before this, nothing ever wrote to audit_events - GET /audit could
    only ever return an empty list no matter what happened. These
    confirm real security-relevant decisions actually get recorded.
    """

    def setUp(self):
        super().setUp()
        self._tmp = tempfile.mkdtemp(prefix="sbg_audit_projects_")
        self._orig_projects_dir = config.STORAGE_DIRS["projects"]
        config.STORAGE_DIRS["projects"] = self._tmp
        self.user = create_user("alice", "password123")
        self.admin = create_user("bob", "password123")
        # create_user always makes "user" role; promote bob directly via DB for this test
        from database import get_connection
        conn = get_connection()
        conn.execute("UPDATE users SET role='admin' WHERE id=?", (self.admin["id"],))
        conn.commit()
        conn.close()
        self.admin["role"] = "admin"

        self.service = ToolService()
        self.audit = AuditService()

    def tearDown(self):
        config.STORAGE_DIRS["projects"] = self._orig_projects_dir
        shutil.rmtree(self._tmp, ignore_errors=True)
        super().tearDown()

    def test_denied_action_is_recorded(self):
        self.service.execute(self.user, "terminal.execute", workspace="proj1", program="python", args=[])
        events = self.audit.list_events(self.user["id"])
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["decision"], "deny")
        self.assertEqual(events[0]["action"], "terminal.execute")

    def test_approval_required_action_is_recorded(self):
        result = self.service.execute(self.admin, "terminal.execute", workspace="proj2", program="python", args=[])
        events = self.audit.list_events(self.admin["id"])
        self.assertEqual(events[0]["decision"], "approval_required")
        self.assertIn(result["approval_id"], events[0]["details"])

    def test_successful_execution_is_recorded(self):
        import subprocess
        from services.tool_service import resolve_workspace_root
        root = resolve_workspace_root("proj3")
        subprocess.run(["git", "init"], cwd=root, capture_output=True, check=True)

        self.service.execute(self.user, "git.read", workspace="proj3")
        events = self.audit.list_events(self.user["id"])
        self.assertEqual(events[0]["decision"], "allow")

    def test_list_all_events_spans_users(self):
        self.service.execute(self.user, "terminal.execute", workspace="proj4", program="python", args=[])
        self.service.execute(self.admin, "terminal.execute", workspace="proj5", program="python", args=[])
        all_events = self.audit.list_all_events()
        user_ids = {e["user_id"] for e in all_events}
        self.assertIn(self.user["id"], user_ids)
        self.assertIn(self.admin["id"], user_ids)

    def test_per_user_list_does_not_leak_other_users_events(self):
        self.service.execute(self.user, "terminal.execute", workspace="proj6", program="python", args=[])
        self.service.execute(self.admin, "terminal.execute", workspace="proj7", program="python", args=[])
        alice_events = self.audit.list_events(self.user["id"])
        self.assertTrue(all(e["user_id"] == self.user["id"] for e in alice_events))
