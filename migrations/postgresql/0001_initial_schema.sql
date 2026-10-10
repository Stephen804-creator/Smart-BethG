-- Smart BethG PostgreSQL baseline migration.
-- Generated from the reviewed schema on 2026-10-10; future schema changes
-- must be added as new numbered migrations and must never rewrite this file.
-- Statements are idempotent to support adopting databases initialized by the
-- earlier compatibility adapter. The migration runner records this version.

CREATE TABLE IF NOT EXISTS users(
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT,
            status TEXT NOT NULL DEFAULT 'active',
            role TEXT NOT NULL DEFAULT 'user',
            session_version INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

CREATE TABLE IF NOT EXISTS agents(
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active'
        );

CREATE TABLE IF NOT EXISTS tasks(
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            request TEXT NOT NULL,
            status TEXT NOT NULL,
            workspace TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

CREATE TABLE IF NOT EXISTS auth_rate_limit_events(
            id SERIAL PRIMARY KEY,
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
            id SERIAL PRIMARY KEY,
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
            id SERIAL PRIMARY KEY,
            user_id INTEGER,
            name TEXT NOT NULL,
            model TEXT NOT NULL,
            credential_ref TEXT,
            status TEXT NOT NULL DEFAULT 'active'
        );

CREATE TABLE IF NOT EXISTS conversations(
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            title TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

CREATE TABLE IF NOT EXISTS messages(
            id SERIAL PRIMARY KEY,
            conversation_id INTEGER NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('user','assistant','system')),
            content TEXT NOT NULL,
            provider TEXT,
            model TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(conversation_id) REFERENCES conversations(id)
        );

CREATE TABLE IF NOT EXISTS provider_calls(
            id SERIAL PRIMARY KEY,
            user_id INTEGER,
            provider TEXT NOT NULL,
            model TEXT,
            success INTEGER NOT NULL,
            latency_ms INTEGER,
            error TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

CREATE TABLE IF NOT EXISTS missions(
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            project_id INTEGER,
            objective TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            priority TEXT NOT NULL DEFAULT 'normal',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

CREATE TABLE IF NOT EXISTS mission_runs(
            id SERIAL PRIMARY KEY,
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
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            path TEXT NOT NULL,
            file_type TEXT,
            source TEXT,
            status TEXT NOT NULL DEFAULT 'stored',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

CREATE TABLE IF NOT EXISTS memory(
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            scope TEXT NOT NULL DEFAULT 'user',
            scope_ref TEXT,
            title TEXT,
            content TEXT NOT NULL,
            source TEXT NOT NULL DEFAULT 'explicit',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

CREATE TABLE IF NOT EXISTS research(
            id SERIAL PRIMARY KEY,
            mission_id INTEGER,
            user_id INTEGER NOT NULL,
            topic TEXT NOT NULL,
            summary TEXT,
            source_info TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(mission_id) REFERENCES missions(id)
        );

CREATE TABLE IF NOT EXISTS evidence(
            id SERIAL PRIMARY KEY,
            mission_id INTEGER,
            user_id INTEGER NOT NULL,
            claim TEXT NOT NULL,
            evidence_text TEXT NOT NULL,
            source_reference TEXT,
            confidence REAL,
            validation_status TEXT NOT NULL DEFAULT 'unvalidated',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(mission_id) REFERENCES missions(id)
        );

CREATE TABLE IF NOT EXISTS workflows(
            id SERIAL PRIMARY KEY,
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
            id SERIAL PRIMARY KEY,
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
            id SERIAL PRIMARY KEY,
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
            id SERIAL PRIMARY KEY,
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
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

CREATE TABLE IF NOT EXISTS logs(
            id SERIAL PRIMARY KEY,
            mission_id INTEGER,
            user_id INTEGER,
            level TEXT NOT NULL DEFAULT 'info',
            event_type TEXT,
            message TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

CREATE TABLE IF NOT EXISTS knowledge_chunks(
            id SERIAL PRIMARY KEY,
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

ALTER TABLE users ADD COLUMN IF NOT EXISTS oauth_provider TEXT;

ALTER TABLE users ADD COLUMN IF NOT EXISTS oauth_subject TEXT;

ALTER TABLE users ADD COLUMN IF NOT EXISTS role TEXT NOT NULL DEFAULT 'user';

ALTER TABLE users ADD COLUMN IF NOT EXISTS session_version INTEGER NOT NULL DEFAULT 0;

ALTER TABLE approvals ADD COLUMN IF NOT EXISTS payload_json TEXT;

ALTER TABLE approvals ADD COLUMN IF NOT EXISTS execution_status TEXT NOT NULL DEFAULT 'pending';

ALTER TABLE approvals ADD COLUMN IF NOT EXISTS expires_at TEXT;

ALTER TABLE approvals ADD COLUMN IF NOT EXISTS decided_at TEXT;

ALTER TABLE approvals ADD COLUMN IF NOT EXISTS executed_at TEXT;

ALTER TABLE approvals ADD COLUMN IF NOT EXISTS execution_result TEXT;

ALTER TABLE missions ADD COLUMN IF NOT EXISTS project_id INTEGER;

ALTER TABLE mission_runs ADD COLUMN IF NOT EXISTS result_json TEXT;

ALTER TABLE mission_runs ADD COLUMN IF NOT EXISTS idempotency_key TEXT;

ALTER TABLE evidence ADD COLUMN IF NOT EXISTS user_id INTEGER;

ALTER TABLE evidence ADD COLUMN IF NOT EXISTS confidence REAL;

ALTER TABLE workflows ADD COLUMN IF NOT EXISTS definition_json TEXT NOT NULL DEFAULT '[]';

ALTER TABLE workflows ADD COLUMN IF NOT EXISTS version INTEGER NOT NULL DEFAULT 1;

ALTER TABLE artifacts ADD COLUMN IF NOT EXISTS content_type TEXT;

ALTER TABLE artifacts ADD COLUMN IF NOT EXISTS size_bytes INTEGER;

ALTER TABLE artifacts ADD COLUMN IF NOT EXISTS checksum_sha256 TEXT;

ALTER TABLE artifacts ADD COLUMN IF NOT EXISTS updated_at TEXT;

ALTER TABLE social_content ADD COLUMN IF NOT EXISTS version INTEGER NOT NULL DEFAULT 1;

ALTER TABLE social_content ADD COLUMN IF NOT EXISTS external_post_id TEXT;

ALTER TABLE social_content ADD COLUMN IF NOT EXISTS published_at TEXT;

ALTER TABLE social_content ADD COLUMN IF NOT EXISTS updated_at TEXT;

ALTER TABLE projects ADD COLUMN IF NOT EXISTS updated_at TEXT;

ALTER TABLE logs ADD COLUMN IF NOT EXISTS user_id INTEGER;

ALTER TABLE messages ADD COLUMN IF NOT EXISTS tokens_in INTEGER;

ALTER TABLE messages ADD COLUMN IF NOT EXISTS tokens_out INTEGER;

ALTER TABLE memory ADD COLUMN IF NOT EXISTS scope TEXT NOT NULL DEFAULT 'user';

ALTER TABLE memory ADD COLUMN IF NOT EXISTS scope_ref TEXT;

ALTER TABLE memory ADD COLUMN IF NOT EXISTS source TEXT NOT NULL DEFAULT 'explicit';

CREATE INDEX IF NOT EXISTS idx_auth_rate_limit_key_epoch
            ON auth_rate_limit_events(key_hash, hit_epoch);

CREATE UNIQUE INDEX IF NOT EXISTS idx_users_oauth_identity ON users(oauth_provider, oauth_subject) WHERE oauth_provider IS NOT NULL AND oauth_subject IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_projects_user_updated ON projects(user_id, updated_at);

CREATE INDEX IF NOT EXISTS idx_missions_user_updated ON missions(user_id, updated_at);

CREATE INDEX IF NOT EXISTS idx_workflows_user_updated ON workflows(user_id, updated_at);

CREATE INDEX IF NOT EXISTS idx_artifacts_user_created ON artifacts(user_id, created_at);

CREATE INDEX IF NOT EXISTS idx_social_content_user_updated ON social_content(user_id, updated_at);

CREATE INDEX IF NOT EXISTS idx_social_content_versions_owner ON social_content_versions(user_id, social_content_id, version);

CREATE INDEX IF NOT EXISTS idx_research_user_created ON research(user_id, created_at);

CREATE INDEX IF NOT EXISTS idx_evidence_user_created ON evidence(user_id, created_at);
