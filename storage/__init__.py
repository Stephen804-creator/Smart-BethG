"""Storage policy for Smart BethG.

This repo intentionally uses a single codebase, but storage access must still be
explicitly owned and scoped to the current user. Files and artifacts should always
move through the storage adapter so the application can later use a local adapter
for development and an S3-compatible/shared backend in production.
"""
from storage.backend import LocalFilesystemStorage, S3CompatibleStorage, get_storage_backend

STORAGE_POLICY = {
    "default_backend": "local",
    "production_backend": "s3-compatible",
    "require_owner_scoping": True,
    "require_namespace_validation": True,
    "rule": (
        "All uploads, reads, deletions, and workspace files must resolve through the "
        "storage adapter and remain inside the owning user's storage root."
    ),
}

__all__ = [
    "LocalFilesystemStorage",
    "S3CompatibleStorage",
    "get_storage_backend",
    "STORAGE_POLICY",
]
