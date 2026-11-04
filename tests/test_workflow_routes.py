"""HTTP-level coverage for workflow publication and immutable version APIs."""
from fastapi.testclient import TestClient

from main_fastapi import create_app
from services.auth_service import create_user
from tests.base import SmartBethGTestCase


class TestWorkflowRoutes(SmartBethGTestCase):
    def setUp(self):
        super().setUp()
        suffix = str(self._tmp_dir).replace("/", "").replace("\\", "")[-8:]
        self.username_one = "workflow-http-a-" + suffix
        self.username_two = "workflow-http-b-" + suffix
        create_user(self.username_one, "workflow-password")
        create_user(self.username_two, "workflow-password")
        self.client_one = TestClient(create_app())
        self.client_two = TestClient(create_app())
        self.csrf_one = self._login(self.client_one, self.username_one)
        self.csrf_two = self._login(self.client_two, self.username_two)

    @staticmethod
    def _login(client, username):
        token = client.get("/auth/csrf").json()["csrf_token"]
        response = client.post(
            "/auth/login",
            headers={"X-CSRF-Token": token},
            json={"username": username, "password": "workflow-password"},
        )
        if response.status_code != 200:
            raise AssertionError("Test login failed: " + response.text)
        return response.json()["csrf_token"]

    def _mutate(self, client, csrf, method, path, **kwargs):
        return client.request(method, path, headers={"X-CSRF-Token": csrf}, **kwargs)


    def test_graph_definition_can_be_created_validated_and_published_via_api(self):
        graph = {
            "format": "smartbethg.workflow.graph",
            "schema_version": "1.0",
            "trigger": {"type": "manual", "version": 1,
                        "input_schema": {"type": "object", "properties": {}}},
            "nodes": [
                {"id": "research-node", "type": "research", "version": 1,
                 "config": {"query": "API graph"}, "inputs": {},
                 "outputs": {"result": {"type": "object"}}},
                {"id": "end-node", "type": "end", "version": 1,
                 "config": {}, "inputs": {}, "outputs": {}},
            ],
            "edges": [
                {"id": "start-edge", "from_node_id": "$trigger", "to_node_id": "research-node"},
                {"id": "finish-edge", "from_node_id": "research-node", "to_node_id": "end-node"},
            ],
        }
        created = self._mutate(
            self.client_one, self.csrf_one, "POST", "/api/v1/workflows",
            json={"name": "Graph API workflow", "graph": graph},
        )
        self.assertEqual(created.status_code, 200, created.text)
        workflow_id = created.json()["id"]
        self.assertEqual(created.json()["graph"]["format"], "smartbethg.workflow.graph")

        validated = self._mutate(
            self.client_one, self.csrf_one, "POST",
            f"/api/v1/workflows/{workflow_id}/validate",
        )
        self.assertEqual(validated.status_code, 200, validated.text)

        published = self._mutate(
            self.client_one, self.csrf_one, "POST",
            f"/api/v1/workflows/{workflow_id}/publish",
        )
        self.assertEqual(published.status_code, 200, published.text)
        snapshot = self.client_one.get(
            f"/api/v1/workflows/{workflow_id}/versions/1"
        )
        self.assertEqual(snapshot.status_code, 200)
        self.assertEqual(snapshot.json()["graph"]["nodes"][0]["id"], "research-node")

    def test_publish_version_history_duplicate_and_run_pin_are_owner_scoped(self):
        created = self._mutate(
            self.client_one, self.csrf_one, "POST", "/api/v1/workflows",
            json={
                "name": "Release workflow",
                "steps": [{"id": "research-v1", "type": "research",
                           "config": {"query": "original release"}}],
            },
        )
        self.assertEqual(created.status_code, 200, created.text)
        workflow_id = created.json()["id"]

        validated = self._mutate(
            self.client_one, self.csrf_one, "POST",
            f"/api/v1/workflows/{workflow_id}/validate",
        )
        self.assertEqual(validated.status_code, 200, validated.text)

        published = self._mutate(
            self.client_one, self.csrf_one, "POST",
            f"/api/v1/workflows/{workflow_id}/publish",
        )
        self.assertEqual(published.status_code, 200, published.text)
        self.assertEqual(published.json()["published_version"], 1)

        versions = self.client_one.get(f"/api/v1/workflows/{workflow_id}/versions")
        self.assertEqual(versions.status_code, 200)
        self.assertEqual([item["version"] for item in versions.json()["versions"]], [1])

        snapshot = self.client_one.get(f"/api/v1/workflows/{workflow_id}/versions/1")
        self.assertEqual(snapshot.status_code, 200)
        self.assertEqual(snapshot.json()["steps"][0]["id"], "research-v1")

        foreign_snapshot = self.client_two.get(
            f"/api/v1/workflows/{workflow_id}/versions/1"
        )
        self.assertEqual(foreign_snapshot.status_code, 404)

        duplicate = self._mutate(
            self.client_one, self.csrf_one, "POST",
            f"/api/v1/workflows/{workflow_id}/duplicate",
            json={"name": "Release workflow copy"},
        )
        self.assertEqual(duplicate.status_code, 200, duplicate.text)
        self.assertEqual(duplicate.json()["status"], "draft")
        self.assertEqual(duplicate.json()["published_version"], None)
        self.assertEqual(duplicate.json()["steps"][0]["id"], "research-v1")

        edited = self._mutate(
            self.client_one, self.csrf_one, "PATCH", f"/api/v1/workflows/{workflow_id}",
            json={"steps": [{"id": "research-v2", "type": "research",
                             "config": {"query": "updated release"}}]},
        )
        self.assertEqual(edited.status_code, 200, edited.text)
        self.assertEqual(edited.json()["status"], "draft")
        self.assertEqual(edited.json()["published_version"], 1)

        unchanged_snapshot = self.client_one.get(
            f"/api/v1/workflows/{workflow_id}/versions/1"
        )
        self.assertEqual(
            unchanged_snapshot.json()["steps"][0]["id"], "research-v1"
        )

        validated_again = self._mutate(
            self.client_one, self.csrf_one, "POST",
            f"/api/v1/workflows/{workflow_id}/validate",
        )
        self.assertEqual(validated_again.status_code, 200)
        published_again = self._mutate(
            self.client_one, self.csrf_one, "POST",
            f"/api/v1/workflows/{workflow_id}/publish",
        )
        self.assertEqual(published_again.status_code, 200)
        self.assertEqual(published_again.json()["published_version"], 2)

        run = self._mutate(
            self.client_one, self.csrf_one, "POST",
            f"/api/v1/workflows/{workflow_id}/runs",
        )
        self.assertEqual(run.status_code, 200, run.text)
        self.assertEqual(run.json()["workflow_version"], 2)
        self.assertIsNotNone(run.json()["workflow_version_id"])


if __name__ == "__main__":
    import unittest
    unittest.main()
