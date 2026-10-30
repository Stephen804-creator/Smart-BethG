"""PDF extraction worker. This module is imported by the separate worker only."""
import io

import config
from repositories.file_repository import FileRepository
from repositories.file_extraction_repository import FileExtractionRepository
from storage.backend import get_storage_backend
from logging_setup import get_logger

logger = get_logger("file_extraction")


def extract_pdf_content(content):
    """Parse a bounded PDF in the worker and return (text, page_count)."""
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(content), strict=False)
    pieces = []
    total = 0
    page_count = min(len(reader.pages), config.MAX_PDF_PAGES)
    for page_number in range(page_count):
        piece = reader.pages[page_number].extract_text() or ""
        remaining = config.MAX_EXTRACTED_TEXT_CHARS - total
        if remaining <= 0:
            break
        pieces.append(piece[:remaining])
        total += min(len(piece), remaining)
        if len(piece) > remaining:
            break
    if len(reader.pages) > config.MAX_PDF_PAGES:
        pieces.append("\n[Smart BethG stopped extraction at the configured page limit.]")
    if total >= config.MAX_EXTRACTED_TEXT_CHARS:
        pieces.append("\n[Smart BethG truncated extraction at the configured text limit.]")
    return "\n".join(pieces), page_count


class FileExtractionService:
    def __init__(self, file_repository=None, extraction_repository=None, storage=None):
        self.files = file_repository or FileRepository()
        self.extractions = extraction_repository or FileExtractionRepository()
        self.storage = storage or get_storage_backend()

    def extract_pdf_job(self, job):
        payload = job.get("payload") or {}
        try:
            file_id = int(payload.get("file_id"))
        except (TypeError, ValueError):
            return {"status": "skipped", "reason": "invalid_file_id"}
        record = self.files.get(file_id, job["user_id"])
        if not record or not str(record.get("filename", "")).lower().endswith(".pdf"):
            return {"status": "skipped", "reason": "file_unavailable"}
        try:
            content = self.storage.get_bytes("uploads", job["user_id"], record["path"])
            if len(content) > config.MAX_UPLOAD_SIZE_BYTES:
                raise ValueError("pdf_size_limit")
            extracted_text, page_count = extract_pdf_content(content)
            if not self.extractions.complete(file_id, job["user_id"], extracted_text, page_count):
                raise RuntimeError("PDF extraction state could not be committed.")
            return {"status": "ready", "file_id": file_id, "page_count": page_count}
        except TimeoutError:
            final_attempt = int(job.get("attempts", 1)) >= int(job.get("max_attempts", 3))
            if final_attempt:
                self.extractions.fail(file_id, job["user_id"], "pdf_extraction_timeout")
            raise
        except Exception as exc:
            logger.warning(
                "PDF extraction failed in worker: user=%s file_id=%s error_type=%s",
                job["user_id"], file_id, type(exc).__name__,
            )
            self.extractions.fail(file_id, job["user_id"], "pdf_extraction_failed")
            return {"status": "failed", "file_id": file_id}
