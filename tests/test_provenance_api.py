"""HTTP and integrity tests for the provenance event timeline."""
from fastapi.testclient import TestClient

from api.dependencies import get_current_user, get_provenance_service
from database import get_connection
from main_fastapi import create_app
from repositories.provenance_repository import ProvenanceRepository
from services.artifact_service import ArtifactService
from services.auth_service import create_user
from services.provenance_service import ProvenanceService
from tests.base import SmartBethGTestCase


class TestProvenanceApi(SmartBethGTestCase):
    def setUp(self):
        super().setUp()
        suffix = str(self._tmp_dir).replace("/", "").replace("\\", "")[-8:]
        self.owner = create_user("provenance-owner-" + suffix, "provenance-password")
        self.other = create_user("provenance-other-" + suffix, "provenance-password")
        self.artifacts = ArtifactService()
        self.artifact = self.artifacts.create(self.owner["id"], "source.txt", "source bytes")
        self.repository = ProvenanceRepository()
        self.service = ProvenanceService(self.repository, self.artifacts)
        self.client = self._client_for(self.owner)
        self.other_client = self._client_for(self.other)

    def _client_for(self, user):
        app = create_app()
        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_provenance_service] = lambda: self.service
        client = TestClient(app)
        client.csrf_token = client.get("/auth/csrf").json()["csrf_token"]
        return client

    def test_authenticated_owner_scoped_event_api(self):
        response = self.client.post(
            f"/api/v1/provenance/artifacts/{self.artifact['id']}/events",
            headers={"X-CSRF-Token": self.client.csrf_token, "Idempotency-Key": "review-once"},
            json={"event_type": "review", "payload": {"summary": "Reviewed the source asset."}},
        )
        self.assertEqual(response.status_code, 201, response.text)
        event = response.json()
        self.assertEqual(event["actor_type"], "human")
        self.assertEqual(event["payload"]["attribution_basis"], "user_supplied")

        timeline = self.client.get(f"/api/v1/provenance/artifacts/{self.artifact['id']}/events")
        self.assertEqual(timeline.status_code, 200, timeline.text)
        self.assertEqual(len(timeline.json()["events"]), 2)  # initial upload + review
        self.assertTrue(timeline.json()["integrity"]["valid"])

        foreign = self.other_client.get(
            f"/api/v1/provenance/artifacts/{self.artifact['id']}/events"
        )
        self.assertEqual(foreign.status_code, 404)

    def test_idempotency_rejects_same_key_with_changed_event(self):
        first = self.repository.append_event(
            self.owner["id"], self.artifact["id"], "review", "human",
            actor_id=str(self.owner["id"]), payload={"summary": "first"},
            idempotency_key="review-fixed-key",
        )
        again = self.repository.append_event(
            self.owner["id"], self.artifact["id"], "review", "human",
            actor_id=str(self.owner["id"]), payload={"summary": "first"},
            idempotency_key="review-fixed-key",
        )
        self.assertEqual(first["id"], again["id"])
        with self.assertRaisesRegex(ValueError, "different provenance event"):
            self.repository.append_event(
                self.owner["id"], self.artifact["id"], "review", "human",
                actor_id=str(self.owner["id"]), payload={"summary": "changed"},
                idempotency_key="review-fixed-key",
            )

    def test_timeline_detects_event_payload_tampering(self):
        self.repository.append_event(
            self.owner["id"], self.artifact["id"], "human_edit", "human",
            actor_id=str(self.owner["id"]), payload={"summary": "Original edit"},
        )
        conn = get_connection()
        try:
            conn.execute(
                "UPDATE provenance_events SET payload_json=? WHERE artifact_id=? AND sequence_number=2",
                ('{"summary":"tampered"}', self.artifact["id"]),
            )
            conn.commit()
        finally:
            conn.close()
        result = self.service.list_timeline(self.owner["id"], self.artifact["id"])
        self.assertFalse(result["integrity"]["valid"])
        self.assertEqual(result["integrity"]["reason"], "payload_digest_mismatch")

    def test_event_mutation_requires_csrf(self):
        response = self.client.post(
            f"/api/v1/provenance/artifacts/{self.artifact['id']}/events",
            json={"event_type": "review", "payload": {}},
        )
        self.assertEqual(response.status_code, 403)


if __name__ == "__main__":
    import unittest
    unittest.main()
