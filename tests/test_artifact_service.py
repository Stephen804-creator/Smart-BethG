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


if __name__ == "__main__":
    import unittest
    unittest.main()
