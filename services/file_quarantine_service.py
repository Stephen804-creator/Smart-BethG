"""Fail-closed intake for untrusted uploads and durable inspection scheduling.

The upload request only stores bytes and atomically queues a separate worker.
It never scans, parses documents, extracts archives, indexes content, or releases
files in the API process.
"""
import hashlib
import os
import re
import uuid

import config
from repositories.file_quarantine_repository import FileQuarantineRepository
from storage.backend import get_storage_backend
from logging_setup import get_logger

logger = get_logger("task")


_TEXT_EXTENSIONS = {
    ".txt", ".md", ".csv", ".json", ".yaml", ".yml", ".py", ".js", ".ts",
    ".tsx", ".jsx", ".html", ".css", ".xml", ".log", ".ini", ".cfg", ".sh",
    ".sql", ".toml", ".java", ".c", ".h", ".cpp", ".hpp", ".rs", ".go",
    ".dart", ".php", ".ps1", ".bat",
}
_IMAGE_SIGNATURES = {
    ".png": (b"\x89PNG\r\n\x1a\n", "image/png"),
    ".jpg": (b"\xff\xd8\xff", "image/jpeg"),
    ".jpeg": (b"\xff\xd8\xff", "image/jpeg"),
    ".gif": ((b"GIF87a", b"GIF89a"), "image/gif"),
}
_ARCHIVE_EXTENSIONS = {".zip"}


def _safe_display_name(filename):
    raw = str(filename or "upload").replace("\\", "/")
    base = raw.rsplit("/", 1)[-1]
    base = re.sub(r"[^A-Za-z0-9._-]", "_", base)[:200]
    if base in {"", ".", ".."}:
        return "upload"
    return base


class FileQuarantineService:
    """Stores validated-size uploads as untrusted, owner-scoped objects."""

    def __init__(self, repository=None, storage=None):
        self.repository = repository or FileQuarantineRepository()
        self.storage = storage or get_storage_backend()

    @staticmethod
    def detect_type(filename, content):
        extension = os.path.splitext(filename.lower())[1]
        if extension in _TEXT_EXTENSIONS:
            if b"\x00" in content:
                raise ValueError("File content does not match its text-file extension.")
            try:
                content.decode("utf-8", errors="strict")
            except UnicodeDecodeError as exc:
                raise ValueError("Text uploads must be valid UTF-8.") from exc
            return "text/plain", "inspection_pending"
        if extension == ".pdf":
            if not content.startswith(b"%PDF-"):
                raise ValueError("File content does not match its PDF extension.")
            return "application/pdf", "scanner_not_configured"
        if extension in _IMAGE_SIGNATURES:
            signatures, media_type = _IMAGE_SIGNATURES[extension]
            if not any(content.startswith(signature) for signature in (signatures if isinstance(signatures, tuple) else (signatures,))):
                raise ValueError("File content does not match its image extension.")
            return media_type, "scanner_not_configured"
        if extension in _ARCHIVE_EXTENSIONS:
            if not content.startswith((b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")):
                raise ValueError("File content does not match its ZIP archive extension.")
            # Never open/extract ZIP content in the API process. An isolated
            # archive-inspection worker must validate paths and expansion limits.
            return "application/zip", "archive_inspection_required"
        raise ValueError("This file type is not accepted for import.")

    def quarantine_upload(self, user_id, filename, content, declared_media_type=None):
        if not isinstance(content, bytes):
            raise ValueError("Upload content must be bytes.")
        if not content:
            raise ValueError("Empty files cannot be imported.")
        if len(content) > config.MAX_UPLOAD_SIZE_BYTES:
            raise ValueError("Uploaded file exceeds the configured size limit.")

        safe_name = _safe_display_name(filename)
        detected_type, reason_code = self.detect_type(safe_name, content)
        quarantine_id = uuid.uuid4().hex
        object_name = quarantine_id + "_" + safe_name
        locator = self.storage.put_bytes("quarantine", user_id, object_name, content)
        record = {
            "id": quarantine_id,
            "user_id": user_id,
            "original_filename": safe_name,
            "object_locator": locator,
            "sha256": hashlib.sha256(content).hexdigest(),
            "byte_size": len(content),
            "detected_media_type": detected_type,
            "declared_media_type": (str(declared_media_type or "")[:255] or None),
            "reason_code": reason_code,
        }
        try:
            saved = self.repository.create(record)
        except Exception:
            # Repository failures can be ambiguous if the database committed
            # but the connection failed while closing. Check before deleting
            # the only stored copy of an upload.
            try:
                saved = self.repository.get(record["id"], user_id)
            except Exception:
                logger.exception("Upload persistence outcome is unknown; preserving quarantine object")
                raise
            if saved:
                return saved
            try:
                self.storage.delete("quarantine", user_id, locator)
            except Exception:
                logger.warning("Orphan quarantine object cleanup failed", exc_info=True)
            raise
        return saved

    def reconcile_abandoned(self):
        return self.repository.reconcile_abandoned_inspections()

    def list_for_user(self, user_id):
        return self.repository.list_for_user(user_id)

    def retry(self, user_id, quarantine_id):
        return self.repository.retry_inspection(quarantine_id, user_id)

    def delete(self, user_id, quarantine_id):
        locator = self.repository.delete(quarantine_id, user_id)
        if not locator:
            return False
        try:
            self.storage.delete("quarantine", user_id, locator)
        except Exception:
            # The row is removed first, so an orphaned opaque object cannot be
            # fetched through the application API. Record it for operational cleanup.
            logger.warning("Quarantine object cleanup failed after metadata deletion: user=%s id=%s", user_id, quarantine_id, exc_info=True)
        return True
