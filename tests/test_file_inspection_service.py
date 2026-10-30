import io
import unittest
import zipfile
from unittest.mock import patch

from services.file_inspection_service import (
    ClamAVScanner,
    InspectionRejected,
    InspectionUnavailable,
    inspect_zip_structure,
)


class FakeSocket:
    def __init__(self, response):
        self.response = response
        self.sent = []
        self.timeout = None

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def settimeout(self, value):
        self.timeout = value

    def sendall(self, value):
        self.sent.append(value)

    def recv(self, _size):
        if self.response is None:
            return b""
        response, self.response = self.response, None
        return response


def make_zip(entries):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries:
            archive.writestr(name, content)
    return stream.getvalue()


class TestClamAVScanner(unittest.TestCase):
    def test_clean_result_requires_explicit_clamav_ok(self):
        fake = FakeSocket(b"stream: OK\0")
        with patch("services.file_inspection_service.socket.create_connection", return_value=fake):
            result = ClamAVScanner(host="scanner", port=3310).scan(b"hello")
        self.assertEqual(result, {"engine": "clamav", "status": "clean"})
        self.assertEqual(fake.sent[0], b"zINSTREAM\0")
        self.assertEqual(fake.sent[-1], b"\0\0\0\0")

    def test_malware_result_is_rejected(self):
        fake = FakeSocket(b"stream: Eicar-Test-Signature FOUND\0")
        with patch("services.file_inspection_service.socket.create_connection", return_value=fake):
            with self.assertRaisesRegex(InspectionRejected, "malware_detected"):
                ClamAVScanner(host="scanner").scan(b"malware")

    def test_missing_scanner_never_returns_clean(self):
        with self.assertRaises(InspectionUnavailable):
            ClamAVScanner(host="").scan(b"file")

    def test_scanner_timeout_is_indeterminate_not_clean(self):
        with patch(
            "services.file_inspection_service.socket.create_connection",
            side_effect=TimeoutError("timeout"),
        ):
            with self.assertRaises(InspectionUnavailable):
                ClamAVScanner(host="scanner").scan(b"file")


class TestZipInspection(unittest.TestCase):
    def test_accepts_small_archive_without_extracting(self):
        result = inspect_zip_structure(make_zip([("src/main.py", b"print('hello')")]))
        self.assertEqual(result["entries"], 1)

    def test_rejects_parent_traversal(self):
        with self.assertRaisesRegex(InspectionRejected, "archive_unsafe_path"):
            inspect_zip_structure(make_zip([("../outside.txt", b"x")]))

    def test_rejects_absolute_path(self):
        with self.assertRaisesRegex(InspectionRejected, "archive_unsafe_path"):
            inspect_zip_structure(make_zip([("/etc/passwd", b"x")]))

    def test_rejects_duplicate_case_insensitive_paths(self):
        with self.assertRaisesRegex(InspectionRejected, "archive_duplicate_path"):
            inspect_zip_structure(make_zip([("Readme.txt", b"a"), ("README.TXT", b"b")]))

    def test_rejects_nested_archives(self):
        with self.assertRaisesRegex(InspectionRejected, "archive_nested_archive_not_supported"):
            inspect_zip_structure(make_zip([("nested.zip", b"PK\x03\x04")]))

    def test_rejects_symlink_entries(self):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w") as archive:
            entry = zipfile.ZipInfo("link")
            entry.create_system = 3
            entry.external_attr = (0o120777 << 16)
            archive.writestr(entry, "target")
        with self.assertRaisesRegex(InspectionRejected, "archive_unsafe_path"):
            inspect_zip_structure(stream.getvalue())

    def test_rejects_actual_expansion_limit(self):
        import config
        old_limit = config.FILE_ARCHIVE_MAX_EXPANDED_BYTES
        config.FILE_ARCHIVE_MAX_EXPANDED_BYTES = 100
        try:
            with self.assertRaisesRegex(InspectionRejected, "archive_expansion_limit"):
                inspect_zip_structure(make_zip([("large.txt", b"x" * 1000)]))
        finally:
            config.FILE_ARCHIVE_MAX_EXPANDED_BYTES = old_limit

    def test_rejects_entry_count_limit(self):
        from config import FILE_ARCHIVE_MAX_ENTRIES
        payload = make_zip([(f"{index}.txt", b"x") for index in range(FILE_ARCHIVE_MAX_ENTRIES + 1)])
        with self.assertRaisesRegex(InspectionRejected, "archive_entry_limit"):
            inspect_zip_structure(payload)


if __name__ == "__main__":
    unittest.main()
