"""Storage adapters for Smart BethG uploads and artifacts."""
from storage.backend import LocalFilesystemStorage, S3CompatibleStorage, get_storage_backend

__all__ = ["LocalFilesystemStorage", "S3CompatibleStorage", "get_storage_backend"]
