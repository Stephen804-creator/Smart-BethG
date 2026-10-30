import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes import files


class FakeQuarantineService:
    def __init__(self):
        self.records = []

    def quarantine_upload(self, user_id, filename, content, declared_media_type=None):
        if filename.lower().endswith(".exe"):
            raise ValueError("This file type is not accepted for import.")
        record = {
            "id": "q-123",
            "user_id": user_id,
            "original_filename": filename,
            "byte_size": len(content),
            "sha256": "a" * 64,
            "detected_media_type": "text/plain",
            "status": "quarantined",
            "inspection_status": "queued",
        }
        self.records.append(record)
        return record

    def list_for_user(self, user_id):
        return [record for record in self.records if record["user_id"] == user_id]

    def delete(self, user_id, quarantine_id):
        return False


class TestFileUploadRoute(unittest.TestCase):
    def setUp(self):
        self.service = FakeQuarantineService()
        app = FastAPI()
        app.include_router(files.router, prefix="/api/v1")
        app.dependency_overrides[files.get_current_user] = lambda: {"id": 41}
        app.dependency_overrides[files.get_file_quarantine_service] = lambda: self.service
        self.client = TestClient(app)
        self.rate_limit_patch = patch.object(files, "check_rate_limit", return_value=True)
        self.rate_limit_patch.start()

    def tearDown(self):
        self.rate_limit_patch.stop()
        self.client.close()

    def test_multipart_upload_returns_quarantine_status_not_trusted_file_id(self):
        response = self.client.post(
            "/api/v1/files",
            files={"file": ("notes.txt", b"private notes", "text/plain")},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["id"], "q-123")
        self.assertEqual(payload["inspection_status"], "queued")
        self.assertNotIn("file_id", payload)
        self.assertEqual(self.service.records[0]["user_id"], 41)

    def test_unsupported_content_returns_415(self):
        response = self.client.post(
            "/api/v1/files",
            files={"file": ("payload.exe", b"MZ payload", "application/octet-stream")},
        )
        self.assertEqual(response.status_code, 415)

    def test_quarantine_listing_is_owner_scoped(self):
        self.client.post(
            "/api/v1/files",
            files={"file": ("notes.txt", b"private notes", "text/plain")},
        )
        response = self.client.get("/api/v1/files/quarantine")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["files"]), 1)
        self.assertEqual(response.json()["files"][0]["inspection_status"], "queued")


if __name__ == "__main__":
    unittest.main()
