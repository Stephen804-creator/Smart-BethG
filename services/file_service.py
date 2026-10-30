"""Owner-scoped file storage, bounded extraction, and budgeted summaries."""
import hashlib
import os
import re
import uuid

import config
from repositories.file_repository import FileRepository
from repositories.file_extraction_repository import FileExtractionRepository
from providers.provider_manager import provider_manager
from providers.model_catalog import model_for_tier
from services.usage_budget_service import UsageBudgetService, BudgetExceededError
from storage.backend import get_storage_backend, StorageError
from logging_setup import get_logger

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
        self.extraction_repo = FileExtractionRepository()
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
            extraction = self.extraction_repo.get_for_user(file_id, user_id)
            if not extraction or extraction["status"] == "pending":
                return None, "PDF extraction is still processing in the background. Please try again shortly."
            if extraction["status"] != "ready":
                return None, "Smart BethG could not extract text from this PDF. The original file is still available to download."
            return extraction.get("extracted_text") or "", None
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
