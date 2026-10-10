"""Provider-neutral artifact storage.

Local storage is for development/single-instance use. S3-compatible storage can
be used with AWS S3, DigitalOcean Spaces, MinIO, or another compatible service.
Only opaque object keys are stored in PostgreSQL; provider credentials never are.
"""
import os
from pathlib import Path


class LocalArtifactStorage:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def put(self, key, content):
        path = self._resolve(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return key

    def get(self, key):
        path = self._resolve(key)
        if not path.is_file():
            raise FileNotFoundError("Artifact object does not exist.")
        return path.read_bytes()

    def delete(self, key):
        path = self._resolve(key)
        path.unlink(missing_ok=True)

    def _resolve(self, key):
        if not isinstance(key, str) or "\\" in key:
            raise ValueError("Invalid artifact storage key.")
        parts = Path(key).parts
        # Keys are owner-prefixed and intentionally flat after the owner ID:
        # <user_id>/<opaque-id>_<safe-name>.<extension>.
        if len(parts) != 2 or not parts[0].isdigit() or parts[1] in {"", ".", ".."}:
            raise ValueError("Artifact storage keys must be owner-scoped.")
        owner_root = self.root / parts[0]
        if owner_root.is_symlink():
            raise ValueError("Artifact owner directory cannot be a symlink.")
        candidate = (self.root / key).resolve()
        resolved_owner = owner_root.resolve()
        if self.root not in resolved_owner.parents or resolved_owner not in candidate.parents:
            raise ValueError("Artifact storage key escapes its owner directory.")
        return candidate


class S3ArtifactStorage:
    def __init__(self, bucket, region=None, endpoint_url=None):
        if not bucket:
            raise RuntimeError("SMART_BETHG_S3_BUCKET is required for S3 object storage.")
        try:
            import boto3
        except ImportError as exc:
            raise RuntimeError("S3 object storage requires boto3 in the production dependencies.") from exc
        self.bucket = bucket
        self.client = boto3.client("s3", region_name=region or None, endpoint_url=endpoint_url or None)

    def put(self, key, content):
        self.client.put_object(Bucket=self.bucket, Key=key, Body=content)
        return key

    def get(self, key):
        response = self.client.get_object(Bucket=self.bucket, Key=key)
        return response["Body"].read()

    def delete(self, key):
        self.client.delete_object(Bucket=self.bucket, Key=key)


def get_artifact_storage():
    backend = os.getenv("SMART_BETHG_OBJECT_STORAGE_BACKEND", "local").strip().lower()
    if backend == "local":
        from config import STORAGE_DIRS
        return LocalArtifactStorage(STORAGE_DIRS["artifacts"])
    if backend in {"s3", "s3-compatible"}:
        return S3ArtifactStorage(
            bucket=os.getenv("SMART_BETHG_S3_BUCKET", ""),
            region=os.getenv("AWS_REGION", ""),
            endpoint_url=os.getenv("SMART_BETHG_S3_ENDPOINT_URL", ""),
        )
    raise RuntimeError("SMART_BETHG_OBJECT_STORAGE_BACKEND must be local or s3-compatible.")
