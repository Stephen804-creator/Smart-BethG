"""
Smart BethG - File Service (T0701 manager, T0702 search, T0703 understanding)

Files are stored under config.STORAGE_DIRS["uploads"]/<user_id>/, one
real file per row in the `files` table (schema-only until now). Nothing
here fakes success: an unsupported file type for text extraction says
so plainly instead of returning garbage or an empty string pretending
to be real content.
"""
import os
import re
import uuid

import config
from repositories.file_repository import FileRepository
from providers.provider_manager import provider_manager
from logging_setup import get_logger

logger = get_logger("task")

# Extensions treated as plain text for search/extraction. Anything else
# (images, archives, unknown binaries) is honestly reported as
# unsupported for content extraction rather than guessed at.
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
    def __init__(self, repo: FileRepository = None):
        self.repo = repo or FileRepository()

    def save_upload(self, user_id, filename, content: bytes, content_type=None):
        if len(content) > config.MAX_UPLOAD_SIZE_BYTES:
            raise ValueError(
                f"File is too large ({len(content)} bytes). "
                f"Maximum is {config.MAX_UPLOAD_SIZE_BYTES} bytes."
            )

        safe_name = _sanitize_filename(filename)
        stored_name = f"{uuid.uuid4().hex}_{safe_name}"
        target_path = os.path.join(_user_upload_dir(user_id), stored_name)

        with open(target_path, "wb") as f:
            f.write(content)

        file_id = self.repo.create(user_id, safe_name, target_path, content_type)
        logger.info("File uploaded: user=%s file_id=%s name=%s bytes=%s", user_id, file_id, safe_name, len(content))
        return self.repo.get(file_id, user_id)

    def list_files(self, user_id):
        return self.repo.list_for_user(user_id)

    def get_file(self, user_id, file_id):
        return self.repo.get(file_id, user_id)

    def read_bytes(self, user_id, file_id):
        record = self.repo.get(file_id, user_id)
        if not record:
            return None, None
        with open(record["path"], "rb") as f:
            return f.read(), record

    def delete_file(self, user_id, file_id):
        record = self.repo.get(file_id, user_id)
        if not record:
            return False
        try:
            os.remove(record["path"])
        except OSError:
            pass  # already gone from disk - DB row removal is what matters for the user
        return self.repo.delete(file_id, user_id)

    def search(self, user_id, query):
        """
        Filename search always; content search additionally for files
        recognized as plain text. Reads matching text files at search
        time rather than maintaining a fake/stale search index.
        """
        query = (query or "").strip()
        if not query:
            return []

        by_name = {f["id"]: f for f in self.repo.search_by_filename(user_id, query)}
        matches = dict(by_name)

        for record in self.repo.list_for_user(user_id):
            if record["id"] in matches:
                continue
            if not self._is_text_file(record["filename"]):
                continue
            try:
                with open(record["path"], "r", encoding="utf-8", errors="ignore") as f:
                    if query.lower() in f.read().lower():
                        matches[record["id"]] = record
            except OSError:
                continue

        return list(matches.values())

    def extract_text(self, user_id, file_id):
        """
        Returns (text_or_None, error_message_or_None). Never fabricates
        content for a file type it can't actually read.
        """
        record = self.repo.get(file_id, user_id)
        if not record:
            return None, "File not found."

        if self._is_text_file(record["filename"]):
            try:
                with open(record["path"], "r", encoding="utf-8", errors="replace") as f:
                    return f.read(), None
            except OSError as exc:
                return None, str(exc)

        if record["filename"].lower().endswith(".pdf"):
            try:
                from pypdf import PdfReader
                reader = PdfReader(record["path"])
                text = "\n".join((page.extract_text() or "") for page in reader.pages)
                return text, None
            except Exception as exc:
                return None, f"Could not extract text from this PDF: {exc}"

        return None, f"Content extraction isn't supported for this file type yet ({record['filename']})."

    def summarize(self, user_id, file_id):
        """
        Real extraction + a real AI call - honestly reports either step
        failing rather than fabricating a summary.
        """
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
        truncated = text[:12000]  # keep the request bounded regardless of file size
        try:
            result = provider.generate(
                [{"role": "user", "content": f"Summarize this file's content concisely:\n\n{truncated}"}],
                model=None,
            )
            return {"summary": result["text"], "error": None}
        except Exception as exc:
            logger.error("File summarization failed: user=%s file_id=%s error=%s", user_id, file_id, exc)
            return {"summary": None, "error": f"Could not reach the AI provider: {exc}"}

    @staticmethod
    def _is_text_file(filename: str) -> bool:
        _, ext = os.path.splitext(filename.lower())
        return ext in TEXT_EXTENSIONS
