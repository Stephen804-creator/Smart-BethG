"""HTTP-level coverage for the project and mission dashboard capability slice."""
from fastapi.testclient import TestClient

from main_fastapi import create_app
from services.auth_service import create_user
from tests.base import SmartBethGTestCase


class TestWorkspaceDashboardHttp(SmartBethGTestCase):
    def setUp(self):
        super().setUp()
        suffix = str(self._tmp_dir).replace("/", "").replace("\\", "")[-8:]
        self.user_one = create_user("dashboard-a-" + suffix, "dashboard-password")
        self.user_two = create_user("dashboard-b-" + suffix, "dashboard-password")
        self.client_one = TestClient(create_app())
        self.client_two = TestClient(create_app())
        self.csrf_one = self._login(self.client_one, "dashboard-a-" + suffix)
        self.csrf_two = self._login(self.client_two, "dashboard-b-" + suffix)

    @staticmethod
    def _login(client, username):
        initial = client.get("/auth/csrf")
        token = initial.json()["csrf_token"]
        response = client.post(
            "/auth/login",
            headers={"X-CSRF-Token": token},
            json={"username": username, "password": "dashboard-password"},
        )
        if response.status_code != 200:
            raise AssertionError("Test login failed: " + response.text)
        return response.json()["csrf_token"]

    def test_home_renders_real_project_and_mission_controls(self):
        response = self.client_one.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn('id="projectCreateForm"', response.text)
        self.assertIn('id="missionCreateForm"', response.text)
        self.assertIn("workspace-dashboard.js", response.text)
        self.assertIn("Projects and missions", response.text)
        self.assertIn("Record a mission", response.text)

    def test_project_and_mission_api_flow_is_owner_scoped(self):
        project_response = self.client_one.post(
            "/api/v1/projects",
            headers={"X-CSRF-Token": self.csrf_one},
            json={"name": "Dashboard project", "description": "Owned by user one"},
        )
        self.assertEqual(project_response.status_code, 200, project_response.text)
        project = project_response.json()

        mission_response = self.client_one.post(
            "/api/v1/missions",
            headers={"X-CSRF-Token": self.csrf_one},
            json={
                "objective": "Track a documentation review",
                "priority": "high",
                "project_id": project["id"],
            },
        )
        self.assertEqual(mission_response.status_code, 200, mission_response.text)
        mission = mission_response.json()
        self.assertEqual(mission["project_id"], project["id"])

        foreign_project = self.client_two.get(f"/api/v1/projects/{project['id']}")
        self.assertEqual(foreign_project.status_code, 404)
        foreign_missions = self.client_two.get("/api/v1/missions")
        self.assertEqual(foreign_missions.status_code, 200)
        self.assertEqual(foreign_missions.json()["missions"], [])

        own_missions = self.client_one.get("/api/v1/missions")
        self.assertEqual(own_missions.status_code, 200)
        self.assertEqual(len(own_missions.json()["missions"]), 1)
        self.assertEqual(own_missions.json()["missions"][0]["project_name"], "Dashboard project")


if __name__ == "__main__":
    import unittest
    unittest.main()
