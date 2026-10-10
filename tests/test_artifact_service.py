import os
from tests.base import SmartBethGTestCase
from services.auth_service import create_user
from services.artifact_service import ArtifactService
from services.artifact_storage import LocalArtifactStorage
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

    def test_binary_artifact_round_trip_and_owner_isolation(self):
        payload = b"\\x89PNG\\r\\n\\x1a\\n" + b"sample-image-data"
        artifact = self.service.create_bytes(
            self.owner["id"], "generated-preview.png", payload, "image/png"
        )
        self.assertEqual(artifact["artifact_type"], "binary")
        self.assertEqual(artifact["content_type"], "image/png")
        self.assertEqual(artifact["size_bytes"], len(payload))
        self.assertIsNone(self.service.get(self.other["id"], artifact["id"]))
        content, record = self.service.read_bytes(self.owner["id"], artifact["id"])
        self.assertEqual(content, payload)
        self.assertEqual(record["checksum_sha256"], __import__("hashlib").sha256(payload).hexdigest())
        self.assertTrue(self.service.delete(self.owner["id"], artifact["id"]))

    def test_binary_artifact_validates_declared_media_signature(self):
        with self.assertRaisesRegex(ValueError, "does not match"):
            self.service.create_bytes(
                self.owner["id"], "fake-image.png", b"this is not a PNG", "image/png"
            )

    def test_binary_artifact_rejects_oversized_payload(self):
        with self.assertRaisesRegex(ValueError, "25 MiB"):
            self.service.create_bytes(
                self.owner["id"], "too-large.mp4",
                b"x" * (self.service.MAX_BINARY_BYTES + 1), "video/mp4"
            )

    def test_binary_artifact_cannot_be_read_as_utf8_text(self):
        artifact = self.service.create_bytes(
            self.owner["id"], "image.png", b"\\x89PNG\\x00", "image/png"
        )
        with self.assertRaisesRegex(ValueError, "download"):
            self.service.read_content(self.owner["id"], artifact["id"])

    def test_local_storage_rejects_owner_path_traversal(self):
        storage = LocalArtifactStorage(config.STORAGE_DIRS["artifacts"])
        with self.assertRaises(ValueError):
            storage.put("../2/secret.txt", b"private")

    def test_local_storage_rejects_symlinked_owner_directory(self):
        root = config.STORAGE_DIRS["artifacts"]
        os.makedirs(os.path.join(root, "2"), exist_ok=True)
        os.symlink(os.path.join(root, "2"), os.path.join(root, "1"))
        storage = LocalArtifactStorage(root)
        with self.assertRaisesRegex(ValueError, "symlink"):
            storage.put("1/secret.txt", b"private")

    def test_artifact_content_limit_is_enforced(self):
        with self.assertRaises(ValueError):
            self.service.create(self.owner["id"], "too-large", "x" * (self.service.MAX_CONTENT_BYTES + 1))


if __name__ == "__main__":
    import unittest
    unittest.main()
