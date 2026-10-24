"""
Smart BethG database access.

PostgreSQL is the only application database in development, testing, and
production. Legacy SQLite databases may be read only by the one-way migration
utility in scripts/migrate_sqlite_to_postgres.py; the application never opens
SQLite files or silently falls back to a second database engine.
"""
import re
from pathlib import Path

import config


SERIAL_ID_TABLES = {
    "users", "agents", "tasks", "auth_rate_limit_events", "audit_events",
    "providers", "conversations", "messages", "provider_calls", "missions",
    "mission_runs", "files", "memory", "research", "evidence", "workflows",
    "artifacts", "social_content", "social_content_versions", "projects", "logs", "connector_installations",
    "knowledge_chunks", "workflow_runs", "decision_ledger", "agent_team_runs",
    "agent_evaluations", "account_lifecycle_requests",
}


class _PostgresCursor:
    def __init__(self, cursor, lastrowid=None):
        self._cursor = cursor
        self.lastrowid = lastrowid
        self.rowcount = cursor.rowcount

    def fetchone(self):
        return self._cursor.fetchone()

    def fetchall(self):
        return self._cursor.fetchall()


class _PostgresConnection:
    """Small compatibility adapter for the repository's parameterized SQL."""
    is_postgres = True

    def __init__(self, connection):
        self._connection = connection

    def execute(self, sql, params=()):
        statement = sql.strip()
        # Repository services use DB-API qmark placeholders. Psycopg uses %s.
        statement = statement.replace("?", "%s")
        lastrowid = None
        insert = re.match(
            r"INSERT\s+INTO\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(([^)]*)\)",
            statement,
            re.I | re.S,
        )
        if insert and not re.search(r"\bRETURNING\b", statement, re.I):
            columns = {
                part.strip().strip(chr(34)).lower()
                for part in insert.group(2).split(",")
            }
            if insert.group(1).lower() in SERIAL_ID_TABLES and "id" not in columns:
                statement += " RETURNING id"
                lastrowid = "__returning_id__"

        cursor = self._connection.execute(statement, params)
        if lastrowid == "__returning_id__":
            row = cursor.fetchone()
            lastrowid = row["id"] if row else None
        return _PostgresCursor(cursor, lastrowid)

    def commit(self):
        self._connection.commit()

    def rollback(self):
        self._connection.rollback()

    def close(self):
        self._connection.close()


def get_connection():
    """Open PostgreSQL or fail clearly; there is no SQLite fallback."""
    database_url = (config.DATABASE_URL or "").strip()
    if not database_url.startswith((
        "postgres://", "postgresql://", "postgresql+psycopg://"
    )):
        raise RuntimeError(
            "Smart BethG requires PostgreSQL in every environment. Set DATABASE_URL "
            "to a local development/test PostgreSQL database or a managed PostgreSQL "
            "instance. SQLite is supported only as a read-only migration source."
        )

    try:
        import psycopg
        from psycopg.rows import dict_row
    except ImportError as exc:
        raise RuntimeError(
            "PostgreSQL is configured but psycopg is not installed. "
            "Install dependencies from requirements.txt."
        ) from exc

    dsn = database_url.replace("postgres://", "postgresql://", 1)
    dsn = dsn.replace("postgresql+psycopg://", "postgresql://", 1)
    return _PostgresConnection(psycopg.connect(dsn, row_factory=dict_row))


def initialize_database():
    """Apply ordered PostgreSQL migrations while serializing application startup."""
    config.ensure_storage_dirs()
    conn = get_connection()
    lock_acquired = False
    try:
        conn.execute("SELECT pg_advisory_lock(734829104)")
        lock_acquired = True
        _run_postgres_migrations(conn)
    finally:
        if lock_acquired:
            try:
                conn.execute("SELECT pg_advisory_unlock(734829104)")
            except Exception:
                pass
        conn.close()


def _run_postgres_migrations(conn):
    """Apply ordered, versioned SQL migrations for PostgreSQL deployments."""
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations ("
        "version TEXT PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP)"
    )
    conn.commit()

    migration_dir = Path(__file__).resolve().parent / "migrations" / "postgresql"
    if not migration_dir.is_dir():
        raise RuntimeError(f"PostgreSQL migration directory is missing: {migration_dir}")

    migration_paths = sorted(migration_dir.glob("[0-9][0-9][0-9][0-9]_*.sql"))
    if not migration_paths:
        raise RuntimeError(f"No PostgreSQL migrations found in {migration_dir}")

    for migration_path in migration_paths:
        version = migration_path.name
        applied = conn.execute(
            "SELECT version FROM schema_migrations WHERE version=? LIMIT 1",
            (version,),
        ).fetchone()
        if applied:
            continue

        sql = migration_path.read_text(encoding="utf-8")
        # Remove full-line comments before splitting; comments can contain
        # semicolons that are not SQL statement delimiters.
        sql = "\n".join(
            line for line in sql.splitlines()
            if not line.lstrip().startswith("--")
        )
        statements = [
            statement.strip()
            for statement in sql.split(";")
            if statement.strip()
        ]
        try:
            for statement in statements:
                conn.execute(statement)
            conn.execute(
                "INSERT INTO schema_migrations(version) VALUES (?)",
                (version,),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
