from tests.base import SmartBethGTestCase
from services.auth_service import create_user
from services.mission_service import MissionService
from services.job_queue import JobQueue

class TestMissionQueueIntegration(SmartBethGTestCase):
    def setUp(self):
        super().setUp(); self.user=create_user("mission-queue-owner","password123")
    def test_plan_validation_and_queue_dispatch(self):
        service=MissionService()
        mission=service.create(self.user["id"],"Search my knowledge",steps=[{"connector_key":"smartbethg","action":"knowledge.search","arguments":{"query":"release checklist","limit":3}}])
        self.assertEqual(mission["steps"][0]["action"],"knowledge.search")
        started=service.start_run(self.user["id"],mission["id"])
        self.assertEqual(started["status"],"running"); self.assertEqual(started["runs"][0]["status"],"running")
        job=next(item for item in JobQueue().list_for_user(self.user["id"]) if item["job_type"]=="mission.execute")
        self.assertEqual(job["status"],"queued")
    def test_unknown_action_cannot_enter_plan(self):
        with self.assertRaises(ValueError):
            MissionService.validate_steps([{"connector_key":"github","action":"shell.run","arguments":{}}])
