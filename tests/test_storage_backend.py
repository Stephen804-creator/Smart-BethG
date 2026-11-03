import os
import tempfile
import unittest
from unittest.mock import Mock

import config
from storage.backend import LocalFilesystemStorage, S3CompatibleStorage, StorageError


class TestLocalFilesystemStorage(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="sbg_storage_")
        self.old_dirs = config.STORAGE_DIRS.copy()
        config.STORAGE_DIRS["uploads"] = os.path.join(self.root, "uploads")
        config.STORAGE_DIRS["artifacts"] = os.path.join(self.root, "artifacts")
        self.storage = LocalFilesystemStorage()

    def tearDown(self):
        import shutil
        config.STORAGE_DIRS.clear()
        config.STORAGE_DIRS.update(self.old_dirs)
        shutil.rmtree(self.root, ignore_errors=True)

    def test_round_trip_and_owner_scoping(self):
        locator = self.storage.put_bytes("uploads", 7, "sample.txt", b"hello")
        self.assertEqual(self.storage.get_bytes("uploads", 7, locator), b"hello")
        with self.assertRaises(StorageError):
            self.storage.get_bytes("uploads", 8, locator)

    def test_file_backed_upload_round_trips(self):
        with tempfile.NamedTemporaryFile(delete=False) as source:
            source.write(b"file-backed-asset")
            source_path = source.name
        try:
            locator = self.storage.put_file("artifacts", 7, "asset.bin", source_path)
            self.assertEqual(self.storage.get_bytes("artifacts", 7, locator), b"file-backed-asset")
        finally:
            os.unlink(source_path)

    def test_rejects_traversal_object_name(self):
        with self.assertRaises(ValueError):
            self.storage.put_bytes("uploads", 7, "../secret.txt", b"no")

    def test_delete_removes_object(self):
        locator = self.storage.put_bytes("uploads", 7, "sample.txt", b"hello")
        self.assertTrue(self.storage.delete("uploads", 7, locator))
        with self.assertRaises(StorageError):
            self.storage.get_bytes("uploads", 7, locator)


class TestS3CompatibleStorage(unittest.TestCase):
    def test_object_key_is_owner_scoped_and_round_trips(self):
        client = Mock()
        client.get_object.return_value = {"Body": Mock(read=Mock(return_value=b"data"))}
        storage = S3CompatibleStorage(bucket="unit-test-bucket", prefix="app", client=client)
        locator = storage.put_bytes("uploads", 9, "item.txt", b"data")
        self.assertEqual(locator, "s3://unit-test-bucket/app/uploads/9/item.txt")
        self.assertEqual(storage.get_bytes("uploads", 9, locator), b"data")
        with self.assertRaises(StorageError):
            storage.get_bytes("uploads", 10, locator)

    def test_file_backed_upload_uses_owner_scoped_s3_key(self):
        with tempfile.NamedTemporaryFile(delete=False) as source:
            source.write(b"s3-file-backed")
            source_path = source.name
        try:
            client = Mock()
            captured = {}
            def capture_upload(stream, bucket, key):
                captured["content"] = stream.read()
                captured["bucket"] = bucket
                captured["key"] = key
            client.upload_fileobj.side_effect = capture_upload
            storage = S3CompatibleStorage(bucket="unit-test-bucket", prefix="app", client=client)
            locator = storage.put_file("artifacts", 9, "asset.bin", source_path)
            self.assertEqual(locator, "s3://unit-test-bucket/app/artifacts/9/asset.bin")
            self.assertEqual(captured, {
                "content": b"s3-file-backed",
                "bucket": "unit-test-bucket",
                "key": "app/artifacts/9/asset.bin",
            })
        finally:
            os.unlink(source_path)

    def test_rejects_foreign_bucket_locator(self):
        storage = S3CompatibleStorage(bucket="unit-test-bucket", client=Mock())
        with self.assertRaises(StorageError):
            storage.get_bytes("uploads", 9, "s3://other-bucket/smartbethg/uploads/9/item.txt")


if __name__ == "__main__":
    unittest.main()
