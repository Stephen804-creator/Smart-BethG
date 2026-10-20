import shutil
import tempfile

import config
from tests.base import SmartBethGTestCase
from services.auth_service import create_user
from services.tool_service import ToolService
from services.audit_service import AuditService


class TestAuditRecording(SmartBethGTestCase):
    def setUp(self):
        super().setUp()
        self._tmp = tempfile.mkdtemp(prefix="sbg_audit_projects_")
        self._orig_projects_dir = config.STORAGE_DIRS["projects"]
        config.STORAGE_DIRS["projects"] = self._tmp
        self.user = create_user("audit-user", "password123")
        self.service = ToolService()
        self.audit = AuditService()

    def tearDown(self):
        config.STORAGE_DIRS["projects"] = self._orig_projects_dir
        shutil.rmtree(self._tmp, ignore_errors=True)
        super().tearDown()

    def test_direct_action_is_blocked_and_audited(self):
        result = self.service.execute(
            self.user, "terminal.execute", workspace="proj1",
            program="python", args=["-c", "print('must not run')"],
        )
        self.assertEqual(result["status"], "unavailable")
        events = self.audit.list_events(self.user["id"])
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["decision"], "blocked")
        self.assertEqual(events[0]["action"], "terminal.execute")

    def test_blocked_events_are_scoped_to_the_requesting_user(self):
        other = create_user("audit-other", "password123")
        self.service.execute(self.user, "git.write", workspace="proj2")
        self.service.execute(other, "git.write", workspace="proj2")
        self.assertEqual(len(self.audit.list_events(self.user["id"])), 1)
        self.assertEqual(len(self.audit.list_events(other["id"])), 1)
