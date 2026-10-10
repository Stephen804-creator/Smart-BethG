"""User-scoped file storage, bounded extraction, and budgeted summaries."""
import hashlib
import os
import re
import uuid
from pathlib import Path

import config
from repositories.file_repository import FileRepository
from providers.provider_manager import provider_manager
from providers.model_catalog import model_for_tier
from services.usage_budget_service import UsageBudgetService, BudgetExceededError
from database import get_connection
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


def _user_upload_dir(user_id) -> str:
    path = os.path.join(config.STORAGE_DIRS["uploads"], str(user_id))
    os.makedirs(path, exist_ok=True)
    return path


class FileService:
    MAX_EXTRACTED_TEXT_CHARS = config.MAX_EXTRACTED_TEXT_CHARS
    MAX_SEARCH_TEXT_CHARS = config.MAX_FILE_SEARCH_CHARS
    MAX_PDF_PAGES = config.MAX_PDF_PAGES

    def __init__(self, repo: FileRepository = None, budget_service: UsageBudgetService = None):
        self.repo = repo or FileRepository()
        self.budget_service = budget_service or UsageBudgetService()

    def save_upload(self, user_id, filename, content: bytes, content_type=None):
        if len(content) > config.MAX_UPLOAD_SIZE_BYTES:
            raise ValueError(
                f"File is too large ({len(content)} bytes). "
                f"Maximum is {config.MAX_UPLOAD_SIZE_BYTES} bytes."
            )

        safe_name = _sanitize_filename(filename)
        stored_name = f"{uuid.uuid4().hex}_{safe_name}"
        target_path = os.path.join(_user_upload_dir(user_id), stored_name)

        with open(target_path, "wb") as handle:
            handle.write(content)

        try:
            file_id = self.repo.create(user_id, safe_name, target_path, content_type)
            record = self.repo.get(file_id, user_id)
        except Exception:
            try:
                os.remove(target_path)
            except OSError:
                pass
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
        path = self._safe_user_path(user_id, record)
        if not path or not path.is_file():
            logger.warning("File path missing or outside owner storage: user=%s file_id=%s", user_id, file_id)
            return None, record
        try:
            if path.stat().st_size > config.MAX_UPLOAD_SIZE_BYTES:
                logger.warning("Stored file exceeds read limit: user=%s file_id=%s", user_id, file_id)
                return None, record
            return path.read_bytes(), record
        except OSError:
            logger.exception("File read failed: user=%s file_id=%s", user_id, file_id)
            return None, record

    def delete_file(self, user_id, file_id):
        record = self.repo.get(file_id, user_id)
        if not record:
            return False
        # Remove the owner-scoped DB record first. If disk deletion fails,
        # an orphan is safer than a live row that points to a missing file.
        deleted = self.repo.delete(file_id, user_id)
        if not deleted:
            return False
        path = self._safe_user_path(user_id, record)
        if path:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                logger.warning("Orphan file cleanup failed: user=%s file_id=%s", user_id, file_id, exc_info=True)
        return True

    def search(self, user_id, query):
        query = (query or "").strip()
        if not query:
            return []
        query = query[:1000]
        by_name = {item["id"]: item for item in self.repo.search_by_filename(user_id, query)}
        matches = dict(by_name)
        for record in self.repo.list_for_user(user_id):
            if record["id"] in matches or not self._is_text_file(record["filename"]):
                continue
            path = self._safe_user_path(user_id, record)
            if not path or not path.is_file():
                continue
            try:
                with path.open("r", encoding="utf-8", errors="ignore") as handle:
                    if query.casefold() in handle.read(self.MAX_SEARCH_TEXT_CHARS).casefold():
                        matches[record["id"]] = record
            except OSError:
                logger.warning("Text search read failed: user=%s file_id=%s", user_id, record["id"], exc_info=True)
        return list(matches.values())

    def extract_text(self, user_id, file_id):
        record = self.repo.get(file_id, user_id)
        if not record:
            return None, "File not found."
        path = self._safe_user_path(user_id, record)
        if not path or not path.is_file():
            logger.warning("Text extraction path missing or outside owner storage: user=%s file_id=%s", user_id, file_id)
            return None, "The stored file is unavailable."

        if self._is_text_file(record["filename"]):
            try:
                with path.open("r", encoding="utf-8", errors="replace") as handle:
                    text = handle.read(self.MAX_EXTRACTED_TEXT_CHARS + 1)
                if len(text) > self.MAX_EXTRACTED_TEXT_CHARS:
                    text = text[:self.MAX_EXTRACTED_TEXT_CHARS] + "\n[Smart BethG truncated extraction at the configured text limit.]"
                return text, None
            except OSError:
                logger.exception("Text extraction failed: user=%s file_id=%s", user_id, file_id)
                return None, "The stored file could not be read."

        if record["filename"].lower().endswith(".pdf"):
            try:
                from pypdf import PdfReader
                reader = PdfReader(str(path), strict=False)
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
                return "\n".join(pieces), None
            except Exception as exc:
                logger.warning("PDF extraction failed: user=%s file_id=%s error_type=%s", user_id, file_id, type(exc).__name__)
                return None, "Could not extract text from this PDF. Check that it is a valid, unencrypted PDF."

        return None, "Content extraction is not supported for this file type yet."

    def summarize(self, user_id, file_id):
        text, error = self.extract_text(user_id, file_id)
        if error:
            return {"summary": None, "error": error}
        provider_name = provider_manager.default_provider_name()
        if not provider_name:
            return {
                "summary": None,
                "error": "Smart BethG isn't connected to an AI model yet, so it can't summarize this file.",
            }
        provider = provider_manager.get(user_id, provider_name)
        model_entry = model_for_tier(provider_name, "balanced")
        model_id = model_entry["id"] if model_entry else None
        messages = [{"role": "user", "content": f"Summarize this file's content concisely:\n\n{text[:12000]}"}]
        reservation = None
        try:
            input_estimate = self.budget_service.estimate_input_tokens(messages)
            reservation = self.budget_service.reserve(
                user_id, provider_name, model_id, input_estimate, config.CHAT_MAX_OUTPUT_TOKENS
            )
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

    def _safe_user_path(self, user_id, record):
        try:
            root = Path(_user_upload_dir(user_id)).resolve()
            path = Path(record["path"]).resolve()
            if root not in path.parents:
                return None
            return path
        except (OSError, TypeError, KeyError):
            return None

    @staticmethod
    def _is_text_file(filename: str) -> bool:
        _, ext = os.path.splitext(filename.lower())
        return ext in TEXT_EXTENSIONS
