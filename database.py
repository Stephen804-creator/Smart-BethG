"""
Smart BethG - Database

PostgreSQL is the production backend; SQLite is retained for local development
and isolated tests. Existing repository SQL uses a small compatibility adapter
to support both while the PostgreSQL migration is completed. The adapter is
not a substitute for PostgreSQL integration tests and versioned schema migrations.

Table groups:
- Application/security: users, agents, tasks, approvals, audit_events,
  tools, providers  (pre-existing)
- Conversations: conversations, messages  (new - backs the real chat
  endpoint; without these, chat history cannot honestly be called
  persistent)
- V1 capability foundations required by Smart_BethG_V1_Capabilities_002.md:
  missions, mission_runs, files, memory, research, evidence, workflows,
  artifacts, social_content, projects, logs

IMPORTANT: creating these tables is schema/storage foundation only. It
Schema presence is not proof that a feature is complete. The dated repository
audit and the corresponding route/service tests are the source of truth for
which capability slices are implemented and which execution paths remain open.
"""
import os
import re
import sqlite3

import config

DB_PATH = config.resolve_sqlite_path()

SERIAL_ID_TABLES = {
    "users", "agents", "tasks", "auth_rate_limit_events", "audit_events",
    "providers", "conversations", "messages", "provider_calls", "missions",
    "mission_runs", "files", "memory", "research", "evidence", "workflows",
    "artifacts", "social_content", "projects", "logs", "knowledge_chunks",
}


class _EmptyCursor:
    """No-op cursor for SQLite-only PRAGMAs on PostgreSQL."""
    rowcount = 0
    lastrowid = None

    def fetchone(self):
        return None

    def fetchall(self):
        return []


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
    """DB-API adapter for the repository's existing parameterized SQL."""
    def __init__(self, connection):
        self._connection = connection
        self.is_postgres = True

    def execute(self, sql, params=()):
        statement = sql.strip()
        if re.match(r"PRAGMA\s+foreign_keys\s*=\s*ON", statement, re.I):
            return _EmptyCursor()
        pragma = re.match(r"PRAGMA\s+table_info\(([^)]+)\)", statement, re.I)
        if pragma:
            table = pragma.group(1).strip().strip(chr(34) + "[]")
            cursor = self._connection.execute(
                "SELECT column_name AS name FROM information_schema.columns "
                "WHERE table_schema = current_schema() AND table_name = %s "
                "ORDER BY ordinal_position",
                (table,),
            )
            return _PostgresCursor(cursor)

        statement = statement.replace("?", "%s")
        lastrowid = None
        insert = re.match(
            r"INSERT\s+INTO\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(([^)]*)\)",
            statement,
            re.I | re.S,
        )
        if insert and not re.search(r"\bRETURNING\b", statement, re.I):
            columns = {part.strip().strip(chr(34)).lower() for part in insert.group(2).split(",")}
            if insert.group(1).lower() in SERIAL_ID_TABLES and "id" not in columns:
                statement += " RETURNING id"
                lastrowid = "__returning_id__"

        cursor = self._connection.execute(statement, params)
        if lastrowid == "__returning_id__":
            row = cursor.fetchone()
            lastrowid = row["id"] if row else None
        return _PostgresCursor(cursor, lastrowid)

    def executescript(self, script):
        clean = "\n".join(
            line for line in script.splitlines()
            if not line.lstrip().startswith("--")
        )
        clean = re.sub(
            r"INTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT",
            "BIGSERIAL PRIMARY KEY",
            clean,
            flags=re.I,
        )
        for statement in clean.split(";"):
            if statement.strip():
                self._connection.execute(statement)

    def commit(self):
        self._connection.commit()

    def rollback(self):
        self._connection.rollback()

    def close(self):
        self._connection.close()


def get_connection():
    """PostgreSQL is required in production; SQLite is the local/test adapter."""
    database_url = (config.DATABASE_URL or "").strip()
    is_postgres = database_url.startswith(("postgres://", "postgresql://", "postgresql+psycopg://"))
    if config.IS_PRODUCTION and not is_postgres:
        raise RuntimeError(
            "Production requires DATABASE_URL pointing to PostgreSQL. "
            "SQLite is supported only for local development and tests."
        )

    if is_postgres:
        try:
            import psycopg
            from psycopg.rows import dict_row
        except ImportError as exc:
            raise RuntimeError(
                "PostgreSQL is configured but psycopg is not installed."
            ) from exc
        dsn = database_url.replace("postgres://", "postgresql://", 1)
        dsn = dsn.replace("postgresql+psycopg://", "postgresql://", 1)
        return _PostgresConnection(psycopg.connect(dsn, row_factory=dict_row))

    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def initialize_database():
    config.ensure_storage_dirs()
    conn = get_connection()
    conn.executescript(
        """
        -- ==================================================
        -- Pre-existing application/security tables
        -- ==================================================
        CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT,
            status TEXT NOT NULL DEFAULT 'active',
            role TEXT NOT NULL DEFAULT 'user',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS agents(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active'
        );

        CREATE TABLE IF NOT EXISTS tasks(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            request TEXT NOT NULL,
            status TEXT NOT NULL,
            workspace TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS auth_rate_limit_events(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key_hash TEXT NOT NULL,
            hit_epoch REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS usage_budget_counters(
            period_start TEXT NOT NULL,
            scope TEXT NOT NULL,
            scope_id TEXT NOT NULL,
            reserved_tokens INTEGER NOT NULL DEFAULT 0,
            actual_tokens INTEGER NOT NULL DEFAULT 0,
            reserved_cost_micros INTEGER NOT NULL DEFAULT 0,
            actual_cost_micros INTEGER NOT NULL DEFAULT 0,
            requests INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(period_start, scope, scope_id)
        );

        CREATE TABLE IF NOT EXISTS usage_budget_reservations(
            id TEXT PRIMARY KEY,
            period_start TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            provider TEXT NOT NULL,
            model TEXT NOT NULL,
            estimated_input_tokens INTEGER NOT NULL,
            estimated_output_tokens INTEGER NOT NULL,
            estimated_cost_micros INTEGER NOT NULL,
            actual_input_tokens INTEGER,
            actual_output_tokens INTEGER,
            actual_cost_micros INTEGER,
            status TEXT NOT NULL DEFAULT 'reserved',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            completed_at TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_auth_rate_limit_key_epoch
            ON auth_rate_limit_events(key_hash, hit_epoch);

        CREATE TABLE IF NOT EXISTS approvals(
            id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            resource TEXT NOT NULL,
            status TEXT NOT NULL,
            payload_json TEXT,
            execution_status TEXT NOT NULL DEFAULT 'pending',
            expires_at TEXT,
            decided_at TEXT,
            executed_at TEXT,
            execution_result TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS audit_events(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            agent_id TEXT,
            action TEXT,
            resource TEXT,
            decision TEXT,
            risk_level TEXT,
            details TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS tools(
            name TEXT PRIMARY KEY,
            description TEXT,
            permission TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS providers(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            name TEXT NOT NULL,
            model TEXT NOT NULL,
            credential_ref TEXT,
            status TEXT NOT NULL DEFAULT 'active'
        );

        -- ==================================================
        -- Conversations (backs the real chat endpoint)
        -- ==================================================
        CREATE TABLE IF NOT EXISTS conversations(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS messages(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('user','assistant','system')),
            content TEXT NOT NULL,
            provider TEXT,
            model TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(conversation_id) REFERENCES conversations(id)
        );

        -- Every provider call attempt (not just the one that ultimately
        -- answered) - backs real model evaluation (T0504) instead of
        -- guessed/assumed reliability.
        CREATE TABLE IF NOT EXISTS provider_calls(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            provider TEXT NOT NULL,
            model TEXT,
            success INTEGER NOT NULL,
            latency_ms INTEGER,
            error TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        -- ==================================================
        -- V1 capability foundations (storage only - see module docstring)
        -- ==================================================
        CREATE TABLE IF NOT EXISTS missions(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            project_id INTEGER,
            objective TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            priority TEXT NOT NULL DEFAULT 'normal',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS mission_runs(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mission_id INTEGER NOT NULL,
            attempt_number INTEGER NOT NULL DEFAULT 1,
            status TEXT NOT NULL DEFAULT 'pending',
            error TEXT,
            started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            completed_at TEXT,
            result_json TEXT,
            idempotency_key TEXT,
            FOREIGN KEY(mission_id) REFERENCES missions(id)
        );

        CREATE TABLE IF NOT EXISTS files(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            path TEXT NOT NULL,
            file_type TEXT,
            source TEXT,
            status TEXT NOT NULL DEFAULT 'stored',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS memory(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            scope TEXT NOT NULL DEFAULT 'user',
            scope_ref TEXT,
            title TEXT,
            content TEXT NOT NULL,
            source TEXT NOT NULL DEFAULT 'explicit',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS research(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mission_id INTEGER,
            user_id INTEGER NOT NULL,
            topic TEXT NOT NULL,
            summary TEXT,
            source_info TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(mission_id) REFERENCES missions(id)
        );

        CREATE TABLE IF NOT EXISTS evidence(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mission_id INTEGER,
            user_id INTEGER NOT NULL,
            claim TEXT NOT NULL,
            evidence_text TEXT NOT NULL,
            source_reference TEXT,
            validation_status TEXT NOT NULL DEFAULT 'unvalidated',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(mission_id) REFERENCES missions(id)
        );

        CREATE TABLE IF NOT EXISTS workflows(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            definition_json TEXT NOT NULL DEFAULT '[]',
            version INTEGER NOT NULL DEFAULT 1,
            status TEXT NOT NULL DEFAULT 'draft',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS artifacts(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mission_id INTEGER,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            artifact_type TEXT,
            path TEXT,
            content_type TEXT,
            size_bytes INTEGER,
            checksum_sha256 TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(mission_id) REFERENCES missions(id)
        );

        CREATE TABLE IF NOT EXISTS social_content(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            platform TEXT NOT NULL,
            topic TEXT,
            caption TEXT,
            hashtags TEXT,
            status TEXT NOT NULL DEFAULT 'draft',
            version INTEGER NOT NULL DEFAULT 1,
            external_post_id TEXT,
            published_at TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS social_content_versions(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            social_content_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            version INTEGER NOT NULL,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            hashtags TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(social_content_id) REFERENCES social_content(id)
        );

        CREATE TABLE IF NOT EXISTS projects(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS logs(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mission_id INTEGER,
            user_id INTEGER,
            level TEXT NOT NULL DEFAULT 'info',
            event_type TEXT,
            message TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        -- Knowledge base (T0901-T0904): chunked, optionally embedded
        -- content from a user's uploaded files, searchable and injected
        -- into chat as grounding context.
        CREATE TABLE IF NOT EXISTS knowledge_chunks(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            file_id INTEGER NOT NULL,
            workspace TEXT NOT NULL DEFAULT 'default',
            chunk_index INTEGER NOT NULL,
            content TEXT NOT NULL,
            embedding TEXT,
            embedding_model TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(file_id) REFERENCES files(id)
        );
        """
    )
    conn.commit()

    # Idempotent migrations for databases created before these columns
    # existed - CREATE TABLE IF NOT EXISTS above doesn't add columns to
    # an already-existing table, so these are applied separately and
    # ignored if the column is already there.
    _add_column_if_missing(conn, "users", "oauth_provider", "TEXT")
    _add_column_if_missing(conn, "users", "oauth_subject", "TEXT")
    _add_column_if_missing(conn, "users", "role", "TEXT NOT NULL DEFAULT 'user'")
    _add_column_if_missing(conn, "approvals", "payload_json", "TEXT")
    _add_column_if_missing(conn, "approvals", "execution_status", "TEXT NOT NULL DEFAULT 'pending'")
    _add_column_if_missing(conn, "approvals", "expires_at", "TEXT")
    _add_column_if_missing(conn, "approvals", "decided_at", "TEXT")
    _add_column_if_missing(conn, "approvals", "executed_at", "TEXT")
    _add_column_if_missing(conn, "approvals", "execution_result", "TEXT")
    _add_column_if_missing(conn, "missions", "project_id", "INTEGER")
    _add_column_if_missing(conn, "mission_runs", "result_json", "TEXT")
    _add_column_if_missing(conn, "mission_runs", "idempotency_key", "TEXT")
    _add_column_if_missing(conn, "evidence", "user_id", "INTEGER")
    _add_column_if_missing(conn, "workflows", "definition_json", "TEXT NOT NULL DEFAULT '[]'")
    _add_column_if_missing(conn, "workflows", "version", "INTEGER NOT NULL DEFAULT 1")
    _add_column_if_missing(conn, "artifacts", "content_type", "TEXT")
    _add_column_if_missing(conn, "artifacts", "size_bytes", "INTEGER")
    _add_column_if_missing(conn, "artifacts", "checksum_sha256", "TEXT")
    _add_column_if_missing(conn, "artifacts", "updated_at", "TEXT")
    _add_column_if_missing(conn, "social_content", "version", "INTEGER NOT NULL DEFAULT 1")
    _add_column_if_missing(conn, "social_content", "external_post_id", "TEXT")
    _add_column_if_missing(conn, "social_content", "published_at", "TEXT")
    _add_column_if_missing(conn, "social_content", "updated_at", "TEXT")
    _add_column_if_missing(conn, "projects", "updated_at", "TEXT")
    _add_column_if_missing(conn, "logs", "user_id", "INTEGER")
    _add_column_if_missing(conn, "messages", "tokens_in", "INTEGER")
    _add_column_if_missing(conn, "messages", "tokens_out", "INTEGER")
    _add_column_if_missing(conn, "memory", "scope", "TEXT NOT NULL DEFAULT 'user'")
    _add_column_if_missing(conn, "memory", "scope_ref", "TEXT")
    _add_column_if_missing(conn, "memory", "source", "TEXT NOT NULL DEFAULT 'explicit'")

    # Owner-scoped lookup indexes are created after additive migrations so
    # existing databases missing a newer column still initialize safely.
    for index_sql in (
        "CREATE INDEX IF NOT EXISTS idx_projects_user_updated ON projects(user_id, updated_at)",
        "CREATE INDEX IF NOT EXISTS idx_missions_user_updated ON missions(user_id, updated_at)",
        "CREATE INDEX IF NOT EXISTS idx_workflows_user_updated ON workflows(user_id, updated_at)",
        "CREATE INDEX IF NOT EXISTS idx_artifacts_user_created ON artifacts(user_id, created_at)",
        "CREATE INDEX IF NOT EXISTS idx_social_content_user_updated ON social_content(user_id, updated_at)",
        "CREATE INDEX IF NOT EXISTS idx_social_content_versions_owner ON social_content_versions(user_id, social_content_id, version)",
        "CREATE INDEX IF NOT EXISTS idx_research_user_created ON research(user_id, created_at)",
        "CREATE INDEX IF NOT EXISTS idx_evidence_user_created ON evidence(user_id, created_at)",
    ):
        conn.execute(index_sql)

    conn.commit()
    conn.close()


def _add_column_if_missing(conn, table, column, coltype):
    existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in existing:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {coltype}")
