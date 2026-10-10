#!/usr/bin/env python3
"""One-way, fail-closed migration from a SQLite database to PostgreSQL.

Run only against a fresh PostgreSQL database after taking a backup of the
source SQLite file. This script never deletes or modifies the SQLite source.
"""
import argparse
import os
import re
import sqlite3
import sys

import psycopg
from psycopg import sql

TABLE_ORDER = [
    "users", "agents", "tasks", "approvals", "audit_events", "tools", "providers",
    "conversations", "messages", "provider_calls", "missions", "mission_runs",
    "files", "memory", "research", "evidence", "workflows", "artifacts",
    "social_content", "projects", "logs", "knowledge_chunks",
]
EXCLUDED_TABLES = {"auth_rate_limit_events", "auth_rate_limit_locks"}
SAFE_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _columns_sqlite(source, table):
    if not SAFE_IDENTIFIER.fullmatch(table):
        raise ValueError(f"Unsafe SQLite table name: {table!r}")
    return [row[1] for row in source.execute(f'PRAGMA table_info("{table}")').fetchall()]


def _columns_postgres(target, table):
    rows = target.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema=current_schema() AND table_name=%s ORDER BY ordinal_position",
        (table,),
    ).fetchall()
    return [row[0] for row in rows]


def _target_has_rows(target, table):
    if not SAFE_IDENTIFIER.fullmatch(table):
        raise ValueError(f"Unsafe PostgreSQL table name: {table!r}")
    return target.execute(
        sql.SQL("SELECT EXISTS (SELECT 1 FROM {} LIMIT 1)").format(sql.Identifier(table))
    ).fetchone()[0]


def _remap_storage_path(value, old_root=None, new_root=None):
    if not isinstance(value, str) or not value or not old_root or not new_root:
        return value
    old_abs = os.path.abspath(old_root)
    value_abs = os.path.abspath(value)
    try:
        if os.path.commonpath([old_abs, value_abs]) != old_abs:
            return value
    except ValueError:
        return value
    return os.path.join(os.path.abspath(new_root), os.path.relpath(value_abs, old_abs))


def migrate(source_path, target_url, dry_run=False, old_storage_root=None, new_storage_root=None):
    if not os.path.isfile(source_path):
        raise FileNotFoundError(f"SQLite source does not exist: {source_path}")
    if not target_url or not target_url.startswith(("postgres://", "postgresql://", "postgresql+psycopg://")):
        raise ValueError("DATABASE_URL must point to PostgreSQL.")

    source = sqlite3.connect(f"file:{os.path.abspath(source_path)}?mode=ro", uri=True)
    source.row_factory = sqlite3.Row
    target = psycopg.connect(
        target_url.replace("postgres://", "postgresql://", 1).replace("postgresql+psycopg://", "postgresql://", 1)
    )
    try:
        available = {
            row[0] for row in source.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
        }
        tables = [t for t in TABLE_ORDER if t in available]
        tables += sorted(available - set(tables) - EXCLUDED_TABLES)

        for table in tables:
            if not SAFE_IDENTIFIER.fullmatch(table):
                raise ValueError(f"Unsafe table name in source: {table!r}")
            if not _columns_postgres(target, table):
                raise RuntimeError(f"Target schema is missing table {table!r}; initialize Smart BethG first.")
            if _target_has_rows(target, table):
                raise RuntimeError(
                    f"Target table {table!r} is not empty. Use a fresh target database; "
                    "this script refuses to merge records silently."
                )

        counts = {}
        for table in tables:
            counts[table] = source.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]

        print("Migration preview:")
        for table, count in counts.items():
            print(f"  {table}: {count} rows")
        if dry_run:
            print("Dry run only: no data copied.")
            return counts

        target.commit()  # close the read-only preflight transaction before the data transaction
        with target.transaction():
            for table in tables:
                source_columns = _columns_sqlite(source, table)
                target_columns = _columns_postgres(target, table)
                columns = [name for name in source_columns if name in target_columns]
                if not columns:
                    continue
                placeholders = sql.SQL(", ").join(sql.Placeholder() for _ in columns)
                statement = sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
                    sql.Identifier(table),
                    sql.SQL(", ").join(sql.Identifier(name) for name in columns),
                    placeholders,
                )
                cursor = source.execute(f'SELECT {", ".join(chr(34)+c+chr(34) for c in columns)} FROM "{table}"')
                for row in cursor:
                    values = []
                    for column in columns:
                        value = row[column]
                        if column in {"path", "file_path", "storage_path"}:
                            value = _remap_storage_path(value, old_storage_root, new_storage_root)
                        values.append(value)
                    target.execute(statement, tuple(values))

            for table in tables:
                if "id" not in _columns_postgres(target, table):
                    continue
                sequence = target.execute("SELECT pg_get_serial_sequence(%s, 'id')", (table,)).fetchone()[0]
                if sequence:
                    target.execute(
                        sql.SQL(
                            "SELECT setval(%s, COALESCE(MAX(id), 1), MAX(id) IS NOT NULL) FROM {}"
                        ).format(sql.Identifier(table)),
                        (sequence,),
                    )

        print("Migration committed. Source SQLite file was left unchanged.")
        return counts
    finally:
        source.close()
        target.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sqlite_path", help="Path to the source SQLite database file")
    parser.add_argument("--dry-run", action="store_true", help="Print row counts without copying data")
    parser.add_argument("--old-storage-root", help="Old root containing uploaded files/workspaces")
    parser.add_argument("--new-storage-root", help="New root after copying the old storage directory")
    args = parser.parse_args()
    if bool(args.old_storage_root) != bool(args.new_storage_root):
        parser.error("--old-storage-root and --new-storage-root must be supplied together")
    try:
        migrate(
            args.sqlite_path, os.getenv("DATABASE_URL", ""), dry_run=args.dry_run,
            old_storage_root=args.old_storage_root, new_storage_root=args.new_storage_root,
        )
    except Exception as exc:
        print(f"Migration failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
