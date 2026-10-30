"""Fail-closed file inspection adapters used only by the isolated worker.

The worker must run in a separately deployed, restricted container/host with
no application secrets beyond the minimum database and private-storage access.
A scanner timeout, missing scanner, malformed response, or archive-policy
failure is never interpreted as a clean result.
"""
import hashlib
import io
import os
import socket
import stat
import struct
import zipfile
import zlib

import config
from repositories.file_quarantine_repository import FileQuarantineRepository
from storage.backend import get_storage_backend
from logging_setup import get_logger

logger = get_logger("file_inspection")


class InspectionUnavailable(RuntimeError):
    """Inspection cannot currently be completed; safe to retry."""


class InspectionRejected(RuntimeError):
    """Inspection completed and the file must not be released."""


class ClamAVScanner:
    def __init__(self, host=None, port=None, timeout=None):
        self.host = host if host is not None else config.FILE_SCANNER_HOST
        self.port = int(port if port is not None else config.FILE_SCANNER_PORT)
        self.timeout = float(timeout if timeout is not None else config.FILE_SCANNER_TIMEOUT_SECONDS)

    def scan(self, content):
        if not self.host:
            raise InspectionUnavailable("Malware scanner is not configured.")
        try:
            with socket.create_connection((self.host, self.port), timeout=self.timeout) as sock:
                sock.settimeout(self.timeout)
                sock.sendall(b"zINSTREAM\0")
                view = memoryview(content)
                for offset in range(0, len(view), 64 * 1024):
                    chunk = view[offset:offset + 64 * 1024]
                    sock.sendall(struct.pack("!I", len(chunk)))
                    sock.sendall(chunk)
                sock.sendall(struct.pack("!I", 0))
                response = bytearray()
                while len(response) < 4096:
                    chunk = sock.recv(1024)
                    if not chunk:
                        break
                    response.extend(chunk)
                    if b"\0" in chunk or b"\n" in chunk:
                        break
        except (OSError, TimeoutError) as exc:
            raise InspectionUnavailable("Malware scanner is temporarily unavailable.") from exc

        result = bytes(response).strip(b"\0\r\n")
        if result.endswith(b": OK"):
            return {"engine": "clamav", "status": "clean"}
        if result.endswith(b": FOUND"):
            raise InspectionRejected("malware_detected")
        if b"ERROR" in result or not result:
            raise InspectionUnavailable("Malware scanner returned an indeterminate result.")
        raise InspectionUnavailable("Malware scanner returned an unrecognized result.")


def inspect_zip_structure(content):
    """Validate ZIP metadata without extracting or writing archive members."""
    max_entries = config.FILE_ARCHIVE_MAX_ENTRIES
    max_expanded = config.FILE_ARCHIVE_MAX_EXPANDED_BYTES
    max_ratio = config.FILE_ARCHIVE_MAX_COMPRESSION_RATIO
    try:
        with zipfile.ZipFile(io.BytesIO(content), "r") as archive:
            entries = archive.infolist()
            if len(entries) > max_entries:
                raise InspectionRejected("archive_entry_limit")
            total_size = 0
            seen = set()
            for entry in entries:
                name = entry.filename.replace("\\", "/")
                parts = name.split("/")
                mode = (entry.external_attr >> 16) & 0xFFFF
                if (
                    name.startswith("/")
                    or not name
                    or any(part in {"", ".", ".."} for part in parts[:-1])
                    or parts[-1] in {".", ".."}
                    or any(len(part) > 1 and part[1] == ":" for part in parts)
                    or stat.S_ISLNK(mode)
                    or (stat.S_IFMT(mode) not in {0, stat.S_IFREG, stat.S_IFDIR})
                ):
                    raise InspectionRejected("archive_unsafe_path")
                normalized = name.casefold()
                if normalized in seen:
                    raise InspectionRejected("archive_duplicate_path")
                seen.add(normalized)
                if entry.flag_bits & 0x1:
                    raise InspectionRejected("archive_encrypted_entry")
                if entry.file_size < 0 or entry.compress_size < 0:
                    raise InspectionRejected("archive_invalid_size")
                if os.path.splitext(name.lower())[1] in {".zip", ".tar", ".gz", ".tgz", ".7z", ".rar"}:
                    raise InspectionRejected("archive_nested_archive_not_supported")
                actual_size = 0
                if not entry.is_dir():
                    # Stream decompression to discard: never write archive paths
                    # to disk, but enforce limits against actual output rather
                    # than trusting only the ZIP central-directory metadata.
                    with archive.open(entry, "r") as member:
                        while True:
                            chunk = member.read(64 * 1024)
                            if not chunk:
                                break
                            actual_size += len(chunk)
                            total_size += len(chunk)
                            if actual_size > entry.file_size or total_size > max_expanded:
                                raise InspectionRejected("archive_expansion_limit")
                if actual_size != entry.file_size:
                    raise InspectionRejected("archive_invalid_size")
                if actual_size and entry.compress_size == 0:
                    raise InspectionRejected("archive_suspicious_ratio")
                if entry.compress_size and actual_size / entry.compress_size > max_ratio:
                    raise InspectionRejected("archive_suspicious_ratio")
    except InspectionRejected:
        raise
    except TimeoutError:
        # The worker's wall-clock guard must trigger a retry/failure state,
        # not mislabel an interrupted inspection as a corrupt archive.
        raise
    except (zipfile.BadZipFile, OSError, RuntimeError, ValueError, EOFError, zlib.error) as exc:
        raise InspectionRejected("archive_invalid") from exc
    return {"entries": len(entries), "expanded_bytes": total_size}


class FileInspectionService:
    def __init__(self, repository=None, storage=None, scanner=None):
        self.repository = repository or FileQuarantineRepository()
        self.storage = storage or get_storage_backend()
        self.scanner = scanner or ClamAVScanner()

    def inspect_job(self, job):
        quarantine_id = str((job.get("payload") or {}).get("quarantine_id") or "")
        expected_hash = str((job.get("payload") or {}).get("sha256") or "")
        record = self.repository.get_for_inspection(quarantine_id, job["user_id"])
        if not record or record["status"] != "quarantined":
            return {"status": "skipped", "reason": "record_unavailable"}
        self.repository.set_inspection_state(quarantine_id, job["user_id"], "checking", attempts=job["attempts"])
        try:
            content = self.storage.get_bytes("quarantine", job["user_id"], record["object_locator"])
            digest = hashlib.sha256(content).hexdigest()
            if digest != record["sha256"] or digest != expected_hash:
                raise InspectionRejected("content_integrity_mismatch")
            archive_result = None
            if record["detected_media_type"] == "application/zip":
                archive_result = inspect_zip_structure(content)
            scan_result = self.scanner.scan(content)
            released = self._release(record, content)
            return {"status": "released", "file_id": released["file_id"], "archive": archive_result}
        except InspectionRejected as exc:
            self.repository.set_inspection_state(
                quarantine_id, job["user_id"], "rejected",
                error_code=str(exc)[:100],
            )
            return {"status": "rejected", "reason_code": str(exc)[:100]}
        except InspectionUnavailable:
            final_attempt = int(job.get("attempts", 1)) >= int(job.get("max_attempts", 5))
            self.repository.set_inspection_state(
                quarantine_id, job["user_id"], "failed" if final_attempt else "queued",
                error_code="scanner_unavailable" if not final_attempt else "scanner_unavailable_after_retries",
            )
            raise
        except Exception:
            logger.exception("Unexpected file inspection failure id=%s", quarantine_id)
            final_attempt = int(job.get("attempts", 1)) >= int(job.get("max_attempts", 5))
            self.repository.set_inspection_state(
                quarantine_id, job["user_id"], "failed" if final_attempt else "queued",
                error_code="inspection_error" if not final_attempt else "inspection_error_after_retries",
            )
            raise

    def _release(self, record, content):
        safe_name = record["original_filename"]
        object_name = record["id"] + "_" + safe_name
        locator = self.storage.put_bytes("uploads", record["user_id"], object_name, content)
        try:
            file_id = self.repository.release(
                record["id"], record["user_id"], safe_name, locator,
                record["detected_media_type"],
            )
        except Exception:
            try:
                self.storage.delete("uploads", record["user_id"], locator)
            except Exception:
                logger.exception("Could not clean up copied file after release failure")
            raise
        try:
            self.storage.delete("quarantine", record["user_id"], record["object_locator"])
        except Exception:
            logger.warning(
                "Released quarantine object cleanup failed: user=%s id=%s",
                record["user_id"], record["id"], exc_info=True,
            )
        return {"file_id": file_id}
