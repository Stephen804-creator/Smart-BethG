from fastapi import HTTPException

from tests.base import SmartBethGTestCase
from services.auth_service import create_user
from services.approval_service import ApprovalService


class TestApprovalService(SmartBethGTestCase):
    def setUp(self):
        super().setUp()
        self.user = create_user("alice", "password123")
        self.service = ApprovalService()

    def test_create_then_persists_across_new_instances(self):
        """
        The bug this replaces: a brand new ApprovalService() per request
        used to mean approvals vanished immediately. A fresh instance
        must still see what an earlier instance created.
        """
        created = self.service.create(self.user["id"], "terminal.execute", "workspace:default")
        fresh_instance = ApprovalService()
        pending = fresh_instance.list_pending(self.user["id"])
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["id"], created["id"])

    def test_decide_approve(self):
        created = self.service.create(self.user["id"], "git.write", "workspace:default")
        result = self.service.decide(created["id"], self.user["id"], True)
        self.assertEqual(result["status"], "approved")
        self.assertTrue(self.service.is_approved(created["id"]))

    def test_decide_reject(self):
        created = self.service.create(self.user["id"], "git.write", "workspace:default")
        result = self.service.decide(created["id"], self.user["id"], False)
        self.assertEqual(result["status"], "rejected")
        self.assertFalse(self.service.is_approved(created["id"]))

    def test_cannot_decide_someone_elses_approval(self):
        other = create_user("bob", "password123")
        created = self.service.create(self.user["id"], "git.write", "workspace:default")
        with self.assertRaises(HTTPException) as caught:
            self.service.decide(created["id"], other["id"], True)
        self.assertEqual(caught.exception.status_code, 404)

    def test_cannot_decide_twice(self):
        created = self.service.create(self.user["id"], "git.write", "workspace:default")
        self.service.decide(created["id"], self.user["id"], True)
        with self.assertRaises(HTTPException) as caught:
            self.service.decide(created["id"], self.user["id"], False)
        self.assertEqual(caught.exception.status_code, 409)

    def test_decided_approval_no_longer_pending(self):
        created = self.service.create(self.user["id"], "git.write", "workspace:default")
        self.service.decide(created["id"], self.user["id"], True)
        self.assertEqual(self.service.list_pending(self.user["id"]), [])

    def test_is_approved_false_for_unknown_id(self):
        self.assertFalse(self.service.is_approved("not-a-real-id"))
