import os
from tests.base import SmartBethGTestCase
from services.auth_service import create_user
from services.artifact_service import ArtifactService
import config


class TestArtifactService(SmartBethGTestCase):
    def setUp(self):
        super().setUp()
        self.owner = create_user("artifact-owner", "password123")
        self.other = create_user("artifact-other", "password123")
        self._old_artifact_dir = config.STORAGE_DIRS["artifacts"]
        config.STORAGE_DIRS["artifacts"] = os.path.join(self._tmp_dir, "artifacts")
        self.service = ArtifactService()

    def tearDown(self):
        config.STORAGE_DIRS["artifacts"] = self._old_artifact_dir
        super().tearDown()

    def test_create_read_and_delete_artifact(self):
        artifact = self.service.create(self.owner["id"], "notes", "important text")
        self.assertEqual(artifact["size_bytes"], len("important text".encode("utf-8")))
        content, _ = self.service.read_content(self.owner["id"], artifact["id"])
        self.assertEqual(content, "important text")
        self.assertEqual(artifact["checksum_sha256"], __import__("hashlib").sha256(b"important text").hexdigest())
        self.assertTrue(self.service.delete(self.owner["id"], artifact["id"]))
        self.assertIsNone(self.service.get(self.owner["id"], artifact["id"]))

    def test_artifact_is_owner_scoped(self):
        artifact = self.service.create(self.owner["id"], "private", "owner-only")
        self.assertIsNone(self.service.get(self.other["id"], artifact["id"]))
        self.assertEqual(self.service.list_for_user(self.other["id"]), [])
        self.assertFalse(self.service.delete(self.other["id"], artifact["id"]))

    def test_json_artifact_has_correct_type_and_rejects_invalid_json(self):
        artifact = self.service.create(self.owner["id"], "settings", '{"enabled": true}', "json")
        self.assertEqual(artifact["content_type"], "application/json; charset=utf-8")
        self.assertTrue(artifact["path"].endswith(".json"))
        with self.assertRaisesRegex(ValueError, "valid JSON"):
            self.service.create(self.owner["id"], "broken", "{bad}", "json")

    def test_read_rejects_content_that_fails_checksum(self):
        artifact = self.service.create(self.owner["id"], "tamper", "original")
        path = os.path.join(config.STORAGE_DIRS["artifacts"], artifact["path"])
        with open(path, "wb") as handle:
            handle.write(b"tampered")
        with self.assertRaisesRegex(ValueError, "integrity check"):
            self.service.read_content(self.owner["id"], artifact["id"])

    def test_artifact_content_limit_is_enforced(self):
        with self.assertRaises(ValueError):
            self.service.create(self.owner["id"], "too-large", "x" * (self.service.MAX_CONTENT_BYTES + 1))


if __name__ == "__main__":
    import unittest
    unittest.main()
