"""Safely migrate local upload/artifact objects to configured shared storage.

Dry-run is the default. This utility never deletes source files; keep them until
a separate backup and recovery check has been completed.
"""
import argparse
from pathlib import Path

import config
from database import get_connection
from storage.backend import get_storage_backend


def _local_source(namespace, locator):
    path = Path(str(locator)).resolve()
    namespace_root = Path(config.STORAGE_DIRS[namespace]).resolve()
    if path == namespace_root or namespace_root not in path.parents:
        raise ValueError(f"Refusing path outside configured {namespace} storage root.")
    if not path.is_file():
        raise FileNotFoundError(f"Local source does not exist: {path}")
    return path


def _records(conn):
    records = []
    for row in conn.execute("SELECT id, user_id, filename, path FROM files ORDER BY id").fetchall():
        records.append(("uploads", dict(row), "files"))
    for row in conn.execute("SELECT id, user_id, name, path FROM artifacts ORDER BY id").fetchall():
        records.append(("artifacts", dict(row), "artifacts"))
    return records


def migrate(apply=False):
    storage = get_storage_backend()
    if not getattr(storage, "shared", False):
        raise RuntimeError("Migration target must be shared storage. Set SMART_BETHG_OBJECT_STORAGE=s3 and configure the bucket.")
    conn = get_connection()
    results = {"examined": 0, "already_shared": 0, "migrated": 0, "failed": 0, "dry_run": not apply}
    try:
        for namespace, row, table in _records(conn):
            results["examined"] += 1
            locator = str(row.get("path") or "")
            if locator.startswith("s3://"):
                results["already_shared"] += 1
                continue
            try:
                source = _local_source(namespace, locator)
                if not apply:
                    print(f"PLAN {table} id={row['id']} owner={row['user_id']} {namespace}/{source.name}")
                    continue
                destination = storage.put_bytes(namespace, row["user_id"], source.name, source.read_bytes())
                try:
                    conn.execute(f"UPDATE {table} SET path=? WHERE id=? AND user_id=? AND path=?",
                                 (destination, row["id"], row["user_id"], locator))
                    conn.commit()
                except Exception:
                    conn.rollback()
                    try:
                        storage.delete(namespace, row["user_id"], destination)
                    except Exception:
                        pass
                    raise
                results["migrated"] += 1
                print(f"MIGRATED {table} id={row['id']} owner={row['user_id']}")
            except Exception as exc:
                results["failed"] += 1
                print(f"FAILED {table} id={row.get('id')}: {type(exc).__name__}: {exc}")
    finally:
        conn.close()
    print("SUMMARY", results)
    if results["failed"]:
        raise SystemExit(1)
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="perform migration; default is dry-run")
    args = parser.parse_args()
    migrate(apply=args.apply)


if __name__ == "__main__":
    main()
