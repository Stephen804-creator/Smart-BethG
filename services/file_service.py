"""Owner-scoped file storage, bounded extraction, and budgeted summaries."""
import hashlib
import io
import os
import re
import uuid

import config
from repositories.file_repository import FileRepository
from providers.provider_manager import provider_manager
from providers.model_catalog import model_for_tier
from services.usage_budget_service import UsageBudgetService, BudgetExceededError
from storage.backend import get_storage_backend, StorageError
from logging_setup import get_logger
from services.ocr_service import extract_image_text, extract_scanned_pdf_text, OCRUnavailable, OCRLimitExceeded

logger = get_logger("task")

TEXT_EXTENSIONS = {
    ".txt", ".md", ".py", ".js", ".json", ".csv", ".yaml", ".yml",
    ".html", ".css", ".xml", ".log", ".ini", ".cfg", ".sh",
}


def _sanitize_filename(filename: str) -> str:
    base = os.path.basename(filename or "upload")
    base = re.sub(r"[^A-Za-z0-9._-]", "_", base)
    return base[:200] or "upload"


class FileService:
    MAX_EXTRACTED_TEXT_CHARS = config.MAX_EXTRACTED_TEXT_CHARS
    MAX_SEARCH_TEXT_CHARS = config.MAX_FILE_SEARCH_CHARS
    MAX_PDF_PAGES = config.MAX_PDF_PAGES

    def __init__(self, repo: FileRepository = None, budget_service: UsageBudgetService = None, storage=None):
        self.repo = repo or FileRepository()
        self.budget_service = budget_service or UsageBudgetService()
        self.storage = storage or get_storage_backend()

    def save_upload(self, user_id, filename, content: bytes, content_type=None):
        if not isinstance(content, bytes):
            raise ValueError("Upload content must be bytes.")
        if len(content) > config.MAX_UPLOAD_SIZE_BYTES:
            raise ValueError(
                f"File is too large ({len(content)} bytes). "
                f"Maximum is {config.MAX_UPLOAD_SIZE_BYTES} bytes."
            )
        safe_name = _sanitize_filename(filename)
        stored_name = f"{uuid.uuid4().hex}_{safe_name}"
        locator = self.storage.put_bytes("uploads", user_id, stored_name, content)
        try:
            file_id = self.repo.create(user_id, safe_name, locator, content_type)
            record = self.repo.get(file_id, user_id)
        except Exception:
            try:
                self.storage.delete("uploads", user_id, locator)
            except Exception:
                logger.warning("Upload cleanup failed after database error", exc_info=True)
            raise
        logger.info("File uploaded: user=%s file_id=%s name=%s bytes=%s", user_id, file_id, safe_name, len(content))
        return record

    def list_files(self, user_id):
        return self.repo.list_for_user(user_id)

    def get_file(self, user_id, file_id):
        return self.repo.get(file_id, user_id)

    def read_bytes(self, user_id, file_id):
        record = self.repo.get(file_id, user_id)
        if not record:
            return None, None
        try:
            content = self.storage.get_bytes("uploads", user_id, record["path"])
            if len(content) > config.MAX_UPLOAD_SIZE_BYTES:
                logger.warning("Stored file exceeds read limit: user=%s file_id=%s", user_id, file_id)
                return None, record
            return content, record
        except (StorageError, OSError, ValueError, KeyError):
            logger.warning("Stored file unavailable or outside owner storage: user=%s file_id=%s", user_id, file_id, exc_info=True)
            return None, record

    def delete_file(self, user_id, file_id):
        record = self.repo.get(file_id, user_id)
        if not record:
            return False
        # Delete the owner-scoped row first: a leftover object is safer than a live row
        # that points at missing data. A failed object deletion is logged for cleanup.
        if not self.repo.delete(file_id, user_id):
            return False
        try:
            self.storage.delete("uploads", user_id, record["path"])
        except Exception:
            logger.warning("Orphan upload cleanup failed: user=%s file_id=%s", user_id, file_id, exc_info=True)
        return True

    def search(self, user_id, query):
        query = (query or "").strip()[:1000]
        if not query:
            return []
        by_name = {item["id"]: item for item in self.repo.search_by_filename(user_id, query)}
        matches = dict(by_name)
        for record in self.repo.list_for_user(user_id):
            if record["id"] in matches or not self._is_text_file(record["filename"]):
                continue
            content, _ = self.read_bytes(user_id, record["id"])
            if content is not None and query.casefold() in content[:self.MAX_SEARCH_TEXT_CHARS].decode("utf-8", errors="ignore").casefold():
                matches[record["id"]] = record
        return list(matches.values())

    def extract_text(self, user_id, file_id):
        record = self.repo.get(file_id, user_id)
        if not record:
            return None, "File not found."
        content, _ = self.read_bytes(user_id, file_id)
        if content is None:
            return None, "The stored file is unavailable."

        if self._is_text_file(record["filename"]):
            text = content[:self.MAX_EXTRACTED_TEXT_CHARS + 1].decode("utf-8", errors="replace")
            if len(text) > self.MAX_EXTRACTED_TEXT_CHARS:
                text = text[:self.MAX_EXTRACTED_TEXT_CHARS] + "\n[Smart BethG truncated extraction at the configured text limit.]"
            return text, None

        if record["filename"].lower().endswith(".pdf"):
            try:
                from pypdf import PdfReader
                reader = PdfReader(io.BytesIO(content), strict=False)
                pieces = []
                total = 0
                for page_number, page in enumerate(reader.pages):
                    if page_number >= self.MAX_PDF_PAGES:
                        pieces.append("\n[Smart BethG stopped extraction at the configured page limit.]")
                        break
                    piece = page.extract_text() or ""
                    remaining = self.MAX_EXTRACTED_TEXT_CHARS - total
                    if remaining <= 0:
                        pieces.append("\n[Smart BethG truncated extraction at the configured text limit.]")
                        break
                    if len(piece) > remaining:
                        pieces.append(piece[:remaining])
                        pieces.append("\n[Smart BethG truncated extraction at the configured text limit.]")
                        break
                    pieces.append(piece)
                    total += len(piece)
                extracted = "\n".join(pieces).strip()
                if extracted:
                    return extracted, None
                # A valid blank PDF should remain a successful empty extraction.
                # Only invoke OCR when the PDF actually contains embedded images.
                has_embedded_images = False
                for page in reader.pages[:self.MAX_PDF_PAGES]:
                    try:
                        if len(page.images):
                            has_embedded_images = True
                            break
                    except Exception:
                        # Some malformed/unsupported image resources cannot be inspected.
                        continue
                if not has_embedded_images:
                    return "", None
                # Image-only/scanned PDFs need optional OCR runtime dependencies.
                try:
                    scanned_text = extract_scanned_pdf_text(content, self.MAX_PDF_PAGES)
                    if scanned_text.strip():
                        return scanned_text, None
                    return None, "No readable text was found. This may be a blank or unsupported scanned PDF."
                except OCRUnavailable:
                    return None, "This PDF appears to contain no selectable text. Install the optional OCR dependencies to read scanned PDFs."
                except OCRLimitExceeded as exc:
                    return None, str(exc)
                except ValueError as exc:
                    logger.info("Scanned PDF OCR unavailable: user=%s file_id=%s error_type=%s", user_id, file_id, type(exc).__name__)
                    return None, str(exc)
            except Exception as exc:
                logger.warning("PDF extraction failed: user=%s file_id=%s error_type=%s", user_id, file_id, type(exc).__name__)
                return None, "Could not extract text from this PDF. Check that it is a valid, unencrypted PDF."
        if os.path.splitext(record["filename"].lower())[1] in {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".bmp"}:
            try:
                text = extract_image_text(content)
                if not text.strip():
                    return None, "No readable text was found in this image."
                return text, None
            except OCRUnavailable:
                return None, "Image OCR is unavailable. Install the optional OCR dependencies to read text in images."
            except (OCRLimitExceeded, ValueError) as exc:
                return None, str(exc)
        return None, "This file type isn't supported for content extraction yet."

    def summarize(self, user_id, file_id):
        text, error = self.extract_text(user_id, file_id)
        if error:
            return {"summary": None, "error": error}
        provider_name = provider_manager.default_provider_name()
        if not provider_name:
            return {"summary": None, "error": "Smart BethG isn't connected to an AI model yet, so it can't summarize this file."}
        provider = provider_manager.get(user_id, provider_name)
        model_entry = model_for_tier(provider_name, "balanced")
        model_id = model_entry["id"] if model_entry else None
        messages = [{"role": "user", "content": f"Summarize this file's content concisely:\n\n{text[:12000]}"}]
        try:
            input_estimate = self.budget_service.estimate_input_tokens(messages)
            reservation = self.budget_service.reserve(user_id, provider_name, model_id, input_estimate, config.CHAT_MAX_OUTPUT_TOKENS)
        except BudgetExceededError:
            return {"summary": None, "error": "The daily usage budget has been reached. Try again after the UTC daily reset."}
        except Exception:
            logger.exception("Could not reserve file-summary usage budget")
            return {"summary": None, "error": "Could not start summarization safely. Please try again later."}
        try:
            result = provider.generate(messages, model=model_id, max_tokens=config.CHAT_MAX_OUTPUT_TOKENS)
        except Exception as exc:
            try:
                self.budget_service.mark_failed(reservation["id"])
            except Exception:
                logger.exception("Could not finalize failed file-summary reservation")
            logger.warning("File summarization failed: user=%s file_id=%s error_type=%s", user_id, file_id, type(exc).__name__)
            return {"summary": None, "error": "Could not reach the AI provider. Please try again later."}
        try:
            self.budget_service.reconcile(reservation["id"], result.get("input_tokens"), result.get("output_tokens"))
        except Exception:
            logger.exception("Could not reconcile file-summary usage; reservation remains conservative")
        return {"summary": result.get("text", ""), "error": None}

    @staticmethod
    def _is_text_file(filename: str) -> bool:
        _, ext = os.path.splitext(filename.lower())
        return ext in TEXT_EXTENSIONS
