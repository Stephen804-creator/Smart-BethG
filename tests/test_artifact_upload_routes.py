"""HTTP tests for bounded, owner-scoped binary artifact uploads."""
import io

from fastapi.testclient import TestClient

from api.dependencies import get_artifact_service, get_current_user
from main_fastapi import create_app
from services.artifact_service import ArtifactService
from repositories.conversation_repository import ConversationRepository
from repositories.provenance_repository import ProvenanceRepository
from services.auth_service import create_user
from tests.base import SmartBethGTestCase


class TestArtifactUploadRoutes(SmartBethGTestCase):
    def setUp(self):
        super().setUp()
        suffix = str(self._tmp_dir).replace("/", "").replace("\\", "")[-8:]
        self.owner = create_user("upload-owner-" + suffix, "upload-password")
        self.other = create_user("upload-other-" + suffix, "upload-password")
        self.service = ArtifactService()
        self.client = self._client_for(self.owner)
        self.other_client = self._client_for(self.other)

    def _client_for(self, user):
        app = create_app()
        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_artifact_service] = lambda: self.service
        client = TestClient(app)
        client.csrf_token = client.get("/auth/csrf").json()["csrf_token"]
        return client

    def test_upload_download_and_owner_isolation(self):
        png = bytes.fromhex("89504e470d0a1a0a") + b"route-test-image"
        response = self.client.post(
            "/api/v1/artifacts/upload",
            headers={"X-CSRF-Token": self.client.csrf_token, "Idempotency-Key": "image-once"},
            data={"name": "route-image.png"},
            files={"file": ("route-image.png", io.BytesIO(png), "image/png")},
        )
        self.assertEqual(response.status_code, 200, response.text)
        artifact = response.json()
        self.assertEqual(artifact["checksum_sha256"], __import__("hashlib").sha256(png).hexdigest())
        self.assertNotIn("path", artifact)

        own_download = self.client.get(f"/api/v1/artifacts/{artifact['id']}/download")
        self.assertEqual(own_download.status_code, 200)
        self.assertEqual(own_download.content, png)
        self.assertEqual(own_download.headers["x-content-type-options"], "nosniff")
        self.assertEqual(own_download.headers["cache-control"], "private, no-store")

        foreign_download = self.other_client.get(f"/api/v1/artifacts/{artifact['id']}/download")
        self.assertEqual(foreign_download.status_code, 404)

    def test_create_asset_from_chat_records_real_execution_metadata(self):
        conversations = ConversationRepository()
        conversation_id = conversations.create(self.owner["id"])
        message_id = conversations.add_message(
            conversation_id, "assistant", "Generated document content",
            provider="openai", model="gpt-test-model",
            orchestrator_id="agent_executor", fallback_used=True,
        )
        response = self.client.post(
            "/api/v1/artifacts/from-chat",
            headers={"X-CSRF-Token": self.client.csrf_token},
            json={
                "name": "generated-document.txt",
                "conversation_id": conversation_id,
                "message_id": message_id,
            },
        )
        self.assertEqual(response.status_code, 201, response.text)
        artifact = response.json()
        self.assertNotIn("path", artifact)
        events = ProvenanceRepository().list_events(self.owner["id"], artifact["id"])
        self.assertEqual([event["event_type"] for event in events], [
            "asset_created", "ai_contribution", "agent_contribution"
        ])
        self.assertEqual(events[1]["provider"], "openai")
        self.assertEqual(events[1]["model"], "gpt-test-model")
        self.assertEqual(events[2]["agent_id"], "agent_executor")

    def test_upload_requires_csrf(self):
        png = bytes.fromhex("89504e470d0a1a0a") + b"csrf-test"
        response = self.client.post(
            "/api/v1/artifacts/upload",
            files={"file": ("csrf.png", io.BytesIO(png), "image/png")},
        )
        self.assertEqual(response.status_code, 403)

    def test_upload_rejects_mime_signature_mismatch(self):
        response = self.client.post(
            "/api/v1/artifacts/upload",
            headers={"X-CSRF-Token": self.client.csrf_token},
            files={"file": ("spoof.png", io.BytesIO(b"not a png"), "image/png")},
        )
        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    import unittest
    unittest.main()
