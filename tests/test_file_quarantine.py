import hashlib
import os
import shutil
import tempfile

import config
from tests.base import SmartBethGTestCase
from services.auth_service import create_user
from services.file_quarantine_service import FileQuarantineService
from services.file_service import FileService
from services.job_queue import JobQueue
from services.file_inspection_service import FileInspectionService


class TestFileQuarantineService(SmartBethGTestCase):
    def setUp(self):
        super().setUp()
        self.root = tempfile.mkdtemp(prefix="sbg_quarantine_")
        self.old_quarantine_dir = config.STORAGE_DIRS["quarantine"]
        self.old_uploads_dir = config.STORAGE_DIRS["uploads"]
        config.STORAGE_DIRS["quarantine"] = self.root
        config.STORAGE_DIRS["uploads"] = self.root + "_trusted"
        suffix = os.path.basename(self._tmp_dir)[-8:]
        self.owner = create_user("quarantine-owner-" + suffix, "password123")
        self.other = create_user("quarantine-other-" + suffix, "password123")
        self.service = FileQuarantineService()

    def tearDown(self):
        config.STORAGE_DIRS["quarantine"] = self.old_quarantine_dir
        config.STORAGE_DIRS["uploads"] = self.old_uploads_dir
        shutil.rmtree(self.root, ignore_errors=True)
        shutil.rmtree(self.root + "_trusted", ignore_errors=True)
        super().tearDown()

    def test_upload_is_quarantined_and_not_added_to_trusted_file_library(self):
        payload = b"Project notes that must not be indexed yet."
        record = self.service.quarantine_upload(
            self.owner["id"], "../../notes.txt", payload, "application/x-executable"
        )
        self.assertEqual(record["status"], "quarantined")
        self.assertEqual(record["original_filename"], "notes.txt")
        self.assertEqual(record["detected_media_type"], "text/plain")
        self.assertEqual(record["declared_media_type"], "application/x-executable")
        self.assertEqual(record["sha256"], hashlib.sha256(payload).hexdigest())
        self.assertEqual(record["byte_size"], len(payload))
        self.assertEqual(record["inspection_status"], "queued")
        self.assertEqual(FileService().list_files(self.owner["id"]), [])
        jobs = JobQueue().list_for_user(self.owner["id"])
        self.assertTrue(any(job["job_type"] == "file.inspect" and job["status"] == "queued" for job in jobs))

    def test_upload_content_is_stored_in_quarantine_namespace(self):
        record = self.service.quarantine_upload(
            self.owner["id"], "readme.md", b"hello"
        )
        owner_root = os.path.join(self.root, str(self.owner["id"]))
        objects = os.listdir(owner_root)
        self.assertEqual(len(objects), 1)
        self.assertTrue(objects[0].startswith(record["id"] + "_"))

    def test_owner_cannot_list_or_delete_another_users_quarantine(self):
        record = self.service.quarantine_upload(
            self.owner["id"], "private.txt", b"private"
        )
        self.assertEqual(self.service.list_for_user(self.other["id"]), [])
        self.assertFalse(self.service.delete(self.other["id"], record["id"]))
        self.assertEqual(len(self.service.list_for_user(self.owner["id"])), 1)


    def test_clean_inspection_releases_file_and_preserves_owner_scope(self):
        record = self.service.quarantine_upload(
            self.owner["id"], "ready.txt", b"safe content"
        )

        class CleanScanner:
            def scan(self, _content):
                return {"engine": "clamav", "status": "clean"}

        job = {
            "user_id": self.owner["id"],
            "attempts": 1,
            "max_attempts": 5,
            "payload": {"quarantine_id": record["id"], "sha256": record["sha256"]},
        }
        result = FileInspectionService(
            repository=self.service.repository,
            storage=self.service.storage,
            scanner=CleanScanner(),
        ).inspect_job(job)

        self.assertEqual(result["status"], "released")
        files = FileService().list_files(self.owner["id"])
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0]["filename"], "ready.txt")
        self.assertEqual(self.service.repository.get(record["id"], self.owner["id"])["status"], "released")
        self.assertEqual(FileService().list_files(self.other["id"]), [])


    def test_failed_inspection_can_be_retried_without_reupload(self):
        record = self.service.quarantine_upload(
            self.owner["id"], "retry.txt", b"keep this upload"
        )
        self.service.repository.set_inspection_state(
            record["id"], self.owner["id"], "failed",
            attempts=5, error_code="scanner_unavailable_after_retries",
        )
        self.assertFalse(self.service.retry(self.other["id"], record["id"]))
        self.assertTrue(self.service.retry(self.owner["id"], record["id"]))
        refreshed = self.service.repository.get(record["id"], self.owner["id"])
        self.assertEqual(refreshed["inspection_status"], "queued")
        self.assertEqual(refreshed["inspection_attempts"], 0)
        jobs = JobQueue().list_for_user(self.owner["id"])
        self.assertEqual(
            len([job for job in jobs if job["job_type"] == "file.inspect"]), 2
        )

    def test_owner_can_delete_their_quarantined_upload(self):
        record = self.service.quarantine_upload(
            self.owner["id"], "remove.txt", b"remove me"
        )
        self.assertTrue(self.service.delete(self.owner["id"], record["id"]))
        self.assertEqual(self.service.list_for_user(self.owner["id"]), [])
        self.assertFalse(self.service.delete(self.owner["id"], record["id"]))

    def test_pdf_signature_is_checked_without_parsing_document(self):
        record = self.service.quarantine_upload(
            self.owner["id"], "document.pdf", b"%PDF-1.7\nmalformed but quarantined"
        )
        self.assertEqual(record["detected_media_type"], "application/pdf")
        self.assertEqual(record["status"], "quarantined")

    def test_image_signature_mismatch_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "does not match"):
            self.service.quarantine_upload(
                self.owner["id"], "image.png", b"not a PNG"
            )

    def test_invalid_utf8_and_binary_text_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "valid UTF-8"):
            self.service.quarantine_upload(self.owner["id"], "notes.txt", b"\xff")
        with self.assertRaisesRegex(ValueError, "does not match"):
            self.service.quarantine_upload(self.owner["id"], "notes.txt", b"abc\x00def")

    def test_zip_is_held_for_isolated_archive_inspection_and_never_extracted(self):
        record = self.service.quarantine_upload(
            self.owner["id"], "source.zip", b"PK\x03\x04untrusted archive bytes"
        )
        self.assertEqual(record["status"], "quarantined")
        self.assertEqual(record["reason_code"], "archive_inspection_required")
        self.assertEqual(record["detected_media_type"], "application/zip")

    def test_zip_with_wrong_signature_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "does not match"):
            self.service.quarantine_upload(
                self.owner["id"], "source.zip", b"not a zip"
            )

    def test_unsupported_extension_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "not accepted"):
            self.service.quarantine_upload(
                self.owner["id"], "payload.exe", b"MZ\x00"
            )

    def test_empty_and_oversized_uploads_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "Empty files"):
            self.service.quarantine_upload(self.owner["id"], "empty.txt", b"")
        previous = config.MAX_UPLOAD_SIZE_BYTES
        config.MAX_UPLOAD_SIZE_BYTES = 4
        try:
            with self.assertRaisesRegex(ValueError, "size limit"):
                self.service.quarantine_upload(self.owner["id"], "large.txt", b"12345")
        finally:
            config.MAX_UPLOAD_SIZE_BYTES = previous


if __name__ == "__main__":
    import unittest
    unittest.main()
