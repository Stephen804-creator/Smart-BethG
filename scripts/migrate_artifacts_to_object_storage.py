"""Safely migrate local artifact files to S3-compatible object storage.

Run from the application environment after backing up PostgreSQL and the local
artifact directory. Default is a read-only dry run; --apply writes and verifies
each object before updating its database locator. Local files are retained unless
--delete-local-after-copy is explicitly supplied.
"""
import argparse
import hashlib
import os
import re
from pathlib import Path

import config
from database import get_connection
from services.artifact_storage import LocalArtifactStorage, S3ArtifactStorage


def local_bytes(root, user_id, stored_path):
    root = Path(root).resolve()
    stored_path = str(stored_path or "")
    if os.path.isabs(stored_path):
        user_root = (root / str(user_id)).resolve()
        path = Path(stored_path).resolve()
        if user_root not in path.parents:
            raise ValueError("Legacy artifact path is outside the owner's directory.")
    else:
        if not stored_path.startswith(f"{user_id}/") or ".." in stored_path.split("/") or "\\" in stored_path:
            raise ValueError("Artifact locator is not owner-scoped.")
        owner_root = root / str(user_id)
        if owner_root.is_symlink():
            raise ValueError("Artifact owner directory cannot be a symlink.")
        path = (root / stored_path).resolve()
        resolved_owner = owner_root.resolve()
        if root not in resolved_owner.parents or resolved_owner not in path.parents:
            raise ValueError("Artifact path escapes the owner's storage directory.")
    if not path.is_file():
        raise FileNotFoundError(f"Local artifact is missing: {path}")
    return path, path.read_bytes()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Copy and update database locators; default is dry run.")
    parser.add_argument("--delete-local-after-copy", action="store_true", help="Delete local files only after verified copy and DB update.")
    args = parser.parse_args()
    if args.delete_local_after_copy and not args.apply:
        parser.error("--delete-local-after-copy requires --apply")
    if not config.DATABASE_URL.startswith(("postgres://", "postgresql://", "postgresql+psycopg://")):
        parser.error("DATABASE_URL must point to the production PostgreSQL database.")
    root = Path(config.STORAGE_DIRS["artifacts"]).resolve()
    target = S3ArtifactStorage(
        bucket=os.getenv("SMART_BETHG_S3_BUCKET", ""),
        region=os.getenv("AWS_REGION", ""),
        endpoint_url=os.getenv("SMART_BETHG_S3_ENDPOINT_URL", ""),
    )
    conn = get_connection()
    copied = 0
    total_bytes = 0
    try:
        rows = conn.execute(
            "SELECT id, user_id, name, path, checksum_sha256 FROM artifacts WHERE path IS NOT NULL ORDER BY id"
        ).fetchall()
        for row in rows:
            record = dict(row)
            old_path, content = local_bytes(root, record["user_id"], record["path"])
            digest = hashlib.sha256(content).hexdigest()
            if not record["checksum_sha256"] or digest != record["checksum_sha256"]:
                raise RuntimeError(f"Artifact {record['id']} failed SHA-256 verification; stopped without updating it.")
            safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", record["name"])[:120] or "artifact"
            suffix = old_path.suffix or ".bin"
            key = f"{record['user_id']}/{record['id']}_{safe_name}{suffix}"
            if args.apply:
                target.put(key, content)
                if hashlib.sha256(target.get(key)).hexdigest() != digest:
                    raise RuntimeError(f"Uploaded artifact {record['id']} failed read-after-write verification.")
                conn.execute(
                    "UPDATE artifacts SET path=?, updated_at=CURRENT_TIMESTAMP WHERE id=? AND user_id=?",
                    (key, record["id"], record["user_id"]),
                )
                conn.commit()
                if args.delete_local_after_copy:
                    old_path.unlink(missing_ok=True)
            copied += 1
            total_bytes += len(content)
            print(f"{'MIGRATED' if args.apply else 'DRY RUN'} artifact_id={record['id']} bytes={len(content)} key={key}")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    print(f"Completed {'migration' if args.apply else 'dry run'}: {copied} artifacts, {total_bytes} bytes.")


if __name__ == "__main__":
    main()
