import os
import shutil
import tempfile

import config
from tests.base import SmartBethGTestCase
from services.auth_service import create_user
from services.file_service import FileService


class TestFileService(SmartBethGTestCase):
    def setUp(self):
        super().setUp()
        self._tmp = tempfile.mkdtemp(prefix="sbg_uploads_")
        self._orig_uploads_dir = config.STORAGE_DIRS["uploads"]
        config.STORAGE_DIRS["uploads"] = self._tmp
        self.user = create_user("alice", "password123")
        self.other = create_user("bob", "password123")
        self.service = FileService()

    def tearDown(self):
        config.STORAGE_DIRS["uploads"] = self._orig_uploads_dir
        shutil.rmtree(self._tmp, ignore_errors=True)
        super().tearDown()

    def test_upload_and_read_back(self):
        record = self.service.save_upload(self.user["id"], "notes.txt", b"hello world", "text/plain")
        self.assertEqual(record["filename"], "notes.txt")
        content, fetched = self.service.read_bytes(self.user["id"], record["id"])
        self.assertEqual(content, b"hello world")

    def test_filename_is_sanitized(self):
        record = self.service.save_upload(self.user["id"], "../../etc/passwd", b"data")
        self.assertEqual(record["filename"], "passwd")
        # And it must actually be stored inside the user's upload dir, not escaped.
        self.assertTrue(record["path"].startswith(self._tmp))

    def test_upload_too_large_rejected(self):
        old_limit = config.MAX_UPLOAD_SIZE_BYTES
        config.MAX_UPLOAD_SIZE_BYTES = 10
        try:
            with self.assertRaises(ValueError):
                self.service.save_upload(self.user["id"], "big.txt", b"x" * 100)
        finally:
            config.MAX_UPLOAD_SIZE_BYTES = old_limit

    def test_list_only_shows_owners_files(self):
        self.service.save_upload(self.user["id"], "mine.txt", b"data")
        self.service.save_upload(self.other["id"], "theirs.txt", b"data")
        mine = self.service.list_files(self.user["id"])
        self.assertEqual(len(mine), 1)
        self.assertEqual(mine[0]["filename"], "mine.txt")

    def test_cannot_read_someone_elses_file(self):
        record = self.service.save_upload(self.other["id"], "secret.txt", b"private")
        content, fetched = self.service.read_bytes(self.user["id"], record["id"])
        self.assertIsNone(content)

    def test_delete_removes_from_disk_and_db(self):
        record = self.service.save_upload(self.user["id"], "temp.txt", b"data")
        path = record["path"]
        self.assertTrue(os.path.exists(path))
        deleted = self.service.delete_file(self.user["id"], record["id"])
        self.assertTrue(deleted)
        self.assertFalse(os.path.exists(path))
        self.assertIsNone(self.service.get_file(self.user["id"], record["id"]))

    def test_cannot_delete_someone_elses_file(self):
        record = self.service.save_upload(self.other["id"], "secret.txt", b"private")
        deleted = self.service.delete_file(self.user["id"], record["id"])
        self.assertFalse(deleted)

    def test_extract_text_from_plain_text_file(self):
        record = self.service.save_upload(self.user["id"], "readme.md", b"# Hello\nWorld")
        text, error = self.service.extract_text(self.user["id"], record["id"])
        self.assertIsNone(error)
        self.assertEqual(text, "# Hello\nWorld")

    def test_extract_text_unsupported_type_is_honest(self):
        record = self.service.save_upload(self.user["id"], "photo.png", b"\x89PNG\r\n fake binary data")
        text, error = self.service.extract_text(self.user["id"], record["id"])
        self.assertIsNone(text)
        self.assertIn("isn't supported", error)

    def test_extract_text_from_real_pdf(self):
        """
        Uses the real pypdf library (now in requirements.txt) end to
        end, not a mock - a blank-but-valid PDF should parse cleanly to
        empty text, proving the extraction path actually works.
        """
        from pypdf import PdfWriter
        import io
        writer = PdfWriter()
        writer.add_blank_page(width=200, height=200)
        buf = io.BytesIO()
        writer.write(buf)
        pdf_bytes = buf.getvalue()

        record = self.service.save_upload(self.user["id"], "doc.pdf", pdf_bytes, "application/pdf")
        text, error = self.service.extract_text(self.user["id"], record["id"])
        self.assertIsNone(error)
        self.assertEqual(text.strip(), "")

    def test_extract_text_from_corrupt_pdf_fails_honestly(self):
        record = self.service.save_upload(self.user["id"], "broken.pdf", b"not a real pdf at all")
        text, error = self.service.extract_text(self.user["id"], record["id"])
        self.assertIsNone(text)
        self.assertIsNotNone(error)

    def test_search_matches_filename(self):
        self.service.save_upload(self.user["id"], "quarterly-report.txt", b"numbers")
        self.service.save_upload(self.user["id"], "other.txt", b"numbers")
        results = self.service.search(self.user["id"], "quarterly")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["filename"], "quarterly-report.txt")

    def test_search_matches_text_content(self):
        self.service.save_upload(self.user["id"], "notes.txt", b"the secret ingredient is basil")
        results = self.service.search(self.user["id"], "basil")
        self.assertEqual(len(results), 1)

    def test_search_does_not_leak_other_users_files(self):
        self.service.save_upload(self.other["id"], "notes.txt", b"the secret ingredient is basil")
        results = self.service.search(self.user["id"], "basil")
        self.assertEqual(results, [])

    def test_summarize_without_provider_is_honest(self):
        record = self.service.save_upload(self.user["id"], "notes.txt", b"some content to summarize")
        result = self.service.summarize(self.user["id"], record["id"])
        self.assertIsNone(result["summary"])
        self.assertIn("isn't connected", result["error"])

    def test_summarize_unsupported_file_type_is_honest(self):
        record = self.service.save_upload(self.user["id"], "photo.png", b"binary data")
        result = self.service.summarize(self.user["id"], record["id"])
        self.assertIsNone(result["summary"])
        self.assertIn("isn't supported", result["error"])
