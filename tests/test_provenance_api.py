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

    def test_source_attachment_uses_owner_scoped_server_hash(self):
        source = self.artifacts.create(self.owner["id"], "source.txt", "original source")
        event = self.service.append_user_event(
            self.owner, self.artifact["id"], "source_attached",
            {"source_artifact_id": source["id"], "summary": "Original source material"},
        )
        import json
        payload = json.loads(event["payload_json"])
        self.assertEqual(payload["source_artifact_id"], source["id"])
        self.assertEqual(payload["source_sha256"], source["checksum_sha256"])
        self.assertEqual(payload["attribution_basis"], "user_supplied")

        foreign_source = self.artifacts.create(self.other["id"], "foreign.txt", "private")
        with self.assertRaisesRegex(ValueError, "Source artifact not found"):
            self.service.append_user_event(
                self.owner, self.artifact["id"], "source_attached",
                {"source_artifact_id": foreign_source["id"]},
            )

    def test_human_edit_instruction_text_is_private_unless_explicitly_included(self):
        import json
        private_default = self.service.append_user_event(
            self.owner, self.artifact["id"], "human_edit",
            {"summary": "Corrected the document structure."},
        )
        private_payload = json.loads(private_default["payload_json"])
        self.assertFalse(private_payload["instruction_text_included"])
        self.assertNotIn("instruction_text", private_payload)

        with self.assertRaisesRegex(ValueError, "private by default"):
            self.service.append_user_event(
                self.owner, self.artifact["id"], "human_edit",
                {"summary": "Edited text", "instruction_text": "private instructions"},
            )

        opted_in = self.service.append_user_event(
            self.owner, self.artifact["id"], "human_edit",
            {
                "summary": "Rewrote the introduction.",
                "include_instruction_text": True,
                "instruction_text": "Use a shorter introduction.",
            },
        )
        opted_payload = json.loads(opted_in["payload_json"])
        self.assertTrue(opted_payload["instruction_text_included"])
        self.assertEqual(opted_payload["instruction_text"], "Use a shorter introduction.")

    def test_approval_is_an_explicit_authenticated_human_event(self):
        event = self.service.append_user_event(
            self.owner, self.artifact["id"], "approval",
            {"summary": "Approved the final version."},
        )
        self.assertEqual(event["actor_type"], "human")
        self.assertEqual(event["actor_id"], str(self.owner["id"]))
        self.assertEqual(event["actor_label"], self.owner["username"])
        self.assertTrue(event["created_at"])

    def test_event_mutation_requires_csrf(self):
        response = self.client.post(
            f"/api/v1/provenance/artifacts/{self.artifact['id']}/events",
            json={"event_type": "review", "payload": {}},
        )
        self.assertEqual(response.status_code, 403)


if __name__ == "__main__":
    import unittest
    unittest.main()
