from tests.base import SmartBethGTestCase
from services.auth_service import create_user
from services.project_service import ProjectService
from services.mission_service import MissionService


class TestMissionService(SmartBethGTestCase):
    def setUp(self):
        super().setUp()
        self.owner = create_user("mission-owner", "password123")
        self.other = create_user("mission-other", "password123")
        self.projects = ProjectService()
        self.service = MissionService()

    def test_mission_run_lifecycle_is_persisted(self):
        project = self.projects.create(self.owner["id"], "Project A")
        mission = self.service.create(self.owner["id"], "Prepare a release plan", project_id=project["id"])
        started = self.service.start_run(self.owner["id"], mission["id"])
        self.assertEqual(started["status"], "running")
        from services.job_queue import JobQueue
        self.assertTrue(any(item["job_type"] == "mission.execute" for item in JobQueue().list_for_user(self.owner["id"])))
        run_id = started["runs"][0]["id"]
        finished = self.service.finish_run(
            self.owner["id"], mission["id"], run_id, "completed",
            result={"summary": "Release plan ready"},
        )
        self.assertEqual(finished["status"], "completed")
        self.assertEqual(finished["runs"][0]["result"]["summary"], "Release plan ready")

    def test_mission_and_project_are_owner_scoped(self):
        project = self.projects.create(self.owner["id"], "Private")
        mission = self.service.create(self.owner["id"], "Private objective", project_id=project["id"])
        self.assertIsNone(self.service.get(self.other["id"], mission["id"]))
        with self.assertRaises(ValueError):
            self.service.create(self.other["id"], "Cross-owner project", project_id=project["id"])

    def test_running_mission_cannot_start_twice(self):
        mission = self.service.create(self.owner["id"], "Run once")
        self.service.start_run(self.owner["id"], mission["id"])
        with self.assertRaises(ValueError):
            self.service.start_run(self.owner["id"], mission["id"])


if __name__ == "__main__":
    import unittest
    unittest.main()
