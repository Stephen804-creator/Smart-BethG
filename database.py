"""
Smart BethG - Database

SQLite-backed persistent storage for V1. DATABASE_URL is a configuration
boundary for a future engine migration (see config.py); only sqlite paths
are accepted today, so a non-SQLite URL fails fast instead of silently
reaching sqlite3.connect().

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
does NOT mean the corresponding intelligence (real web research, workflow
execution, artifact generation, memory retrieval, etc.) is implemented.
See v1_capabilities.md status vocabulary - these are STRUCTURALLY
PREPARED, not IMPLEMENTED, until real logic reads/writes them.
"""
import sqlite3

import config

DB_PATH = config.resolve_sqlite_path()


def get_connection():
    import os
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
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
            password_hash TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
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

        CREATE TABLE IF NOT EXISTS approvals(
            id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            resource TEXT NOT NULL,
            status TEXT NOT NULL,
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

        -- ==================================================
        -- V1 capability foundations (storage only - see module docstring)
        -- ==================================================
        CREATE TABLE IF NOT EXISTS missions(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
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
            title TEXT,
            content TEXT NOT NULL,
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
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
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
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS projects(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS logs(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mission_id INTEGER,
            level TEXT NOT NULL DEFAULT 'info',
            event_type TEXT,
            message TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    conn.commit()
    conn.close()
