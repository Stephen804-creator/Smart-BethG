"""Owner-scoped storage adapters with local and S3-compatible implementations.

Database rows store an opaque locator. Callers must still fetch the row through
an owner-scoped repository before asking the adapter to read or delete it.
"""
from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

import config

_NAMESPACE_RE = re.compile(r"^[a-z][a-z0-9_-]{0,39}$")
_OWNER_RE = re.compile(r"^[A-Za-z0-9_-]{1,100}$")
_OBJECT_RE = re.compile(r"^[A-Za-z0-9._-]{1,240}$")


class StorageError(RuntimeError):
    """A safe, user-facing storage operation failure."""


class LocalFilesystemStorage:
    """Single-instance/local adapter; resolves every object inside its owner root."""

    shared = False

    def _owner_root(self, namespace, owner_id):
        if namespace not in config.STORAGE_DIRS or not _NAMESPACE_RE.fullmatch(namespace):
            raise ValueError("Unknown storage namespace.")
        owner = str(owner_id)
        if not _OWNER_RE.fullmatch(owner):
            raise ValueError("Invalid storage owner.")
        root = Path(config.STORAGE_DIRS[namespace]).resolve()
        owner_root = (root / owner).resolve()
        if owner_root != root and root not in owner_root.parents:
            raise ValueError("Invalid storage owner path.")
        owner_root.mkdir(parents=True, exist_ok=True)
        return owner_root

    def put_bytes(self, namespace, owner_id, object_name, content):
        if not _OBJECT_RE.fullmatch(str(object_name or "")):
            raise ValueError("Invalid storage object name.")
        if not isinstance(content, bytes):
            raise TypeError("Storage content must be bytes.")
        root = self._owner_root(namespace, owner_id)
        target = (root / object_name).resolve()
        if root not in target.parents:
            raise ValueError("Storage path escapes its owner directory.")
        fd, temporary = tempfile.mkstemp(prefix=".upload-", dir=str(root))
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, target)
        except Exception:
            try:
                os.unlink(temporary)
            except OSError:
                pass
            raise
        return str(target)

    def _resolve_locator(self, namespace, owner_id, locator):
        root = self._owner_root(namespace, owner_id)
        try:
            path = Path(str(locator)).resolve()
        except (OSError, TypeError, ValueError) as exc:
            raise StorageError("Stored object locator is invalid.") from exc
        if root not in path.parents:
            raise StorageError("Stored object is outside the owner's storage area.")
        return path

    def get_bytes(self, namespace, owner_id, locator):
        path = self._resolve_locator(namespace, owner_id, locator)
        try:
            return path.read_bytes()
        except FileNotFoundError as exc:
            raise StorageError("Stored object is unavailable.") from exc
        except OSError as exc:
            raise StorageError("Stored object could not be read.") from exc

    def delete(self, namespace, owner_id, locator):
        path = self._resolve_locator(namespace, owner_id, locator)
        try:
            path.unlink(missing_ok=True)
            return True
        except OSError as exc:
            raise StorageError("Stored object could not be deleted.") from exc


class S3CompatibleStorage:
    """Shared object storage using S3 API (AWS S3 or compatible providers)."""

    shared = True

    def __init__(self, bucket=None, prefix=None, endpoint_url=None, region_name=None, client=None):
        self.bucket = (bucket if bucket is not None else os.getenv("SMART_BETHG_S3_BUCKET", "")).strip()
        self.prefix = (prefix if prefix is not None else os.getenv("SMART_BETHG_S3_PREFIX", "smartbethg")).strip("/")
        self.endpoint_url = endpoint_url if endpoint_url is not None else os.getenv("SMART_BETHG_S3_ENDPOINT_URL") or None
        self.region_name = region_name if region_name is not None else os.getenv("SMART_BETHG_S3_REGION", "us-east-1")
        if not self.bucket:
            raise RuntimeError("SMART_BETHG_S3_BUCKET is required when object storage is set to s3.")
        if not re.fullmatch(r"[A-Za-z0-9._-]{3,255}", self.bucket):
            raise RuntimeError("SMART_BETHG_S3_BUCKET contains invalid characters.")
        if client is None:
            try:
                import boto3
            except ImportError as exc:
                raise RuntimeError("S3 storage requires boto3; install the application requirements.") from exc
            client = boto3.client("s3", endpoint_url=self.endpoint_url, region_name=self.region_name)
        self.client = client

    def _key(self, namespace, owner_id, object_name):
        if not _NAMESPACE_RE.fullmatch(str(namespace or "")):
            raise ValueError("Unknown storage namespace.")
        owner = str(owner_id)
        if not _OWNER_RE.fullmatch(owner) or not _OBJECT_RE.fullmatch(str(object_name or "")):
            raise ValueError("Invalid owner or storage object name.")
        return "/".join(part for part in (self.prefix, namespace, owner, object_name) if part)

    def _validated_key(self, namespace, owner_id, locator):
        parsed = urlsplit(str(locator or ""))
        if parsed.scheme != "s3" or parsed.netloc != self.bucket or not parsed.path.startswith("/"):
            raise StorageError("Stored object locator is invalid.")
        key = parsed.path.lstrip("/")
        expected_prefix = "/".join(part for part in (self.prefix, namespace, str(owner_id)) if part) + "/"
        if not key.startswith(expected_prefix) or ".." in key.split("/"):
            raise StorageError("Stored object is outside the owner's storage area.")
        return key

    def put_bytes(self, namespace, owner_id, object_name, content):
        if not isinstance(content, bytes):
            raise TypeError("Storage content must be bytes.")
        key = self._key(namespace, owner_id, object_name)
        try:
            self.client.put_object(Bucket=self.bucket, Key=key, Body=content)
        except Exception as exc:
            raise StorageError("Object storage upload failed.") from exc
        return f"s3://{self.bucket}/{key}"

    def get_bytes(self, namespace, owner_id, locator):
        key = self._validated_key(namespace, owner_id, locator)
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=key)
            return response["Body"].read()
        except Exception as exc:
            raise StorageError("Stored object could not be read.") from exc

    def delete(self, namespace, owner_id, locator):
        key = self._validated_key(namespace, owner_id, locator)
        try:
            self.client.delete_object(Bucket=self.bucket, Key=key)
            return True
        except Exception as exc:
            raise StorageError("Stored object could not be deleted.") from exc


def get_storage_backend():
    """Create the configured adapter; configuration is read at call time for tests."""
    backend = os.getenv("SMART_BETHG_OBJECT_STORAGE", "local").strip().lower()
    if backend == "local":
        return LocalFilesystemStorage()
    if backend in {"s3", "s3-compatible"}:
        return S3CompatibleStorage()
    raise RuntimeError("SMART_BETHG_OBJECT_STORAGE must be 'local' or 's3'.")
