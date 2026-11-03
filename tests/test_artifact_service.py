import os
import os\nimport tempfile\n\nfrom tests.base import SmartBethGTestCase
from services.auth_service import create_user
from services.artifact_service import ArtifactService\nfrom repositories.provenance_repository import ProvenanceRepository
import config


class TestArtifactService(SmartBethGTestCase):
    def setUp(self):
        super().setUp()
        self.owner = create_user("artifact-owner", "password123")
        self.other = create_user("artifact-other", "password123")
        self.service = ArtifactService()

    def test_create_read_and_delete_artifact(self):
        artifact = self.service.create(self.owner["id"], "notes", "important text")
        self.assertEqual(artifact["size_bytes"], len("important text".encode("utf-8")))
        content, _ = self.service.read_content(self.owner["id"], artifact["id"])
        self.assertEqual(content, "important text")
        self.assertTrue(self.service.delete(self.owner["id"], artifact["id"]))
        self.assertIsNone(self.service.get(self.owner["id"], artifact["id"]))

    def test_artifact_is_owner_scoped(self):
        artifact = self.service.create(self.owner["id"], "private", "owner-only")
        self.assertIsNone(self.service.get(self.other["id"], artifact["id"]))
        self.assertEqual(self.service.list_for_user(self.other["id"]), [])
        self.assertFalse(self.service.delete(self.other["id"], artifact["id"]))

    def test_artifact_content_limit_is_enforced(self):
        with self.assertRaises(ValueError):
            self.service.create(self.owner["id"], "too-large", "x" * (self.service.MAX_CONTENT_BYTES + 1))

    def _temporary_asset(self, content):
        handle = tempfile.NamedTemporaryFile(delete=False)
        try:
            handle.write(content)
            handle.close()
            return handle.name
        except Exception:
            handle.close()
            os.unlink(handle.name)
            raise

    def test_binary_image_upload_records_checksum_and_provenance(self):
        png = bytes.fromhex("89504e470d0a1a0a") + b"test-image-data"
        path = self._temporary_asset(png)
        try:
            artifact = self.service.create_binary_from_path(
                self.owner["id"], "portrait.png", path, "image/png"
            )
            self.assertEqual(artifact["artifact_type"], "image")
            self.assertEqual(artifact["content_type"], "image/png")
            self.assertEqual(artifact["checksum_sha256"], __import__("hashlib").sha256(png).hexdigest())
            content, record = self.service.read_bytes(self.owner["id"], artifact["id"])
            self.assertEqual(content, png)
            self.assertEqual(record["id"], artifact["id"])
            events = ProvenanceRepository().list_events(self.owner["id"], artifact["id"])
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0]["event_type"], "asset_uploaded")
        finally:
            os.unlink(path)

    def test_binary_upload_rejects_mismatched_media_signature(self):
        path = self._temporary_asset(b"not a png")
        try:
            with self.assertRaisesRegex(ValueError, "signature does not match"):
                self.service.create_binary_from_path(
                    self.owner["id"], "spoof.png", path, "image/png"
                )
        finally:
            os.unlink(path)

    def test_binary_upload_enforces_configured_size_limit(self):
        import config
        handle = tempfile.NamedTemporaryFile(delete=False)
        path = handle.name
        handle.close()
        try:
            with open(path, "wb") as output:
                output.truncate(config.MAX_ASSET_UPLOAD_BYTES + 1)
            with self.assertRaisesRegex(ValueError, "size limit"):
                self.service.create_binary_from_path(
                    self.owner["id"], "large.txt", path, "text/plain"
                )
        finally:
            os.unlink(path)

    def test_binary_asset_read_is_owner_scoped(self):
        png = bytes.fromhex("89504e470d0a1a0a") + b"owner-data"
        path = self._temporary_asset(png)
        try:
            artifact = self.service.create_binary_from_path(
                self.owner["id"], "private.png", path, "image/png"
            )
            content, record = self.service.read_bytes(self.other["id"], artifact["id"])
            self.assertIsNone(content)
            self.assertIsNone(record)
        finally:
            os.unlink(path)

    def test_binary_upload_idempotency_rejects_changed_content(self):
        first_path = self._temporary_asset(bytes.fromhex("89504e470d0a1a0a") + b"first")
        second_path = self._temporary_asset(bytes.fromhex("89504e470d0a1a0a") + b"second")
        try:
            first = self.service.create_binary_from_path(
                self.owner["id"], "same.png", first_path, "image/png", idempotency_key="asset-once"
            )
            again = self.service.create_binary_from_path(
                self.owner["id"], "same.png", first_path, "image/png", idempotency_key="asset-once"
            )
            self.assertEqual(first["id"], again["id"])
            with self.assertRaisesRegex(ValueError, "different asset content"):
                self.service.create_binary_from_path(
                    self.owner["id"], "same.png", second_path, "image/png", idempotency_key="asset-once"
                )
        finally:
            os.unlink(first_path)
            os.unlink(second_path)


if __name__ == "__main__":
    import unittest
    unittest.main()
