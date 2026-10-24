from tests.base import SmartBethGTestCase
from services.auth_service import create_user
from services.job_queue import JobQueue

class TestDurableJobQueue(SmartBethGTestCase):
    def setUp(self):
        super().setUp(); self.user=create_user("queue-owner","password123"); self.queue=JobQueue()
    def test_enqueue_is_idempotent_for_same_user_key(self):
        first=self.queue.enqueue(self.user["id"],"mission.execute",{"mission_id":9,"run_id":2},"test-run-2")
        second=self.queue.enqueue(self.user["id"],"mission.execute",{"mission_id":9,"run_id":2},"test-run-2")
        self.assertEqual(first["id"],second["id"])
        self.assertEqual(len([j for j in self.queue.list_for_user(self.user["id"]) if j["idempotency_key"]=="test-run-2"]),1)
    def test_claim_and_complete_are_lease_guarded(self):
        created=self.queue.enqueue(self.user["id"],"mission.execute",{"mission_id":10,"run_id":3},"test-run-3")
        job=self.queue.claim(); self.assertIsNotNone(job); self.assertEqual(job["id"],created["id"])
        self.assertTrue(self.queue.complete(job,{"status":"ok"}))
        self.assertFalse(self.queue.complete(job,{"status":"duplicate"}))
        self.assertEqual(self.queue.get_for_user(self.user["id"],created["id"])["status"],"succeeded")
