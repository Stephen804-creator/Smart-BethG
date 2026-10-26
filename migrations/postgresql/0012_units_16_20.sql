-- Units 16-20: organizations/workspaces, controlled sandbox records,
-- social publishing schedules, and request-level operational telemetry.
CREATE TABLE IF NOT EXISTS organizations (
 id BIGSERIAL PRIMARY KEY,
 name TEXT NOT NULL CHECK (length(trim(name)) BETWEEN 1 AND 120),
 slug TEXT NOT NULL UNIQUE CHECK (slug ~ '^[a-z0-9][a-z0-9-]{1,58}[a-z0-9]$'),
 owner_user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
 created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS organization_members (
 id BIGSERIAL PRIMARY KEY,
 organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
 user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 role TEXT NOT NULL CHECK (role IN ('owner','admin','member','viewer')),
 invited_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
 created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
 UNIQUE (organization_id,user_id)
);
CREATE INDEX IF NOT EXISTS idx_org_members_user ON organization_members(user_id, organization_id);
CREATE TABLE IF NOT EXISTS workspaces (
 id BIGSERIAL PRIMARY KEY,
 organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
 name TEXT NOT NULL CHECK (length(trim(name)) BETWEEN 1 AND 120),
 slug TEXT NOT NULL CHECK (slug ~ '^[a-z0-9][a-z0-9-]{1,58}[a-z0-9]$'),
 status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','archived')),
 created_by INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
 created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
 UNIQUE (organization_id,slug)
);
CREATE INDEX IF NOT EXISTS idx_workspaces_org ON workspaces(organization_id,status);
CREATE TABLE IF NOT EXISTS workspace_members (
 id BIGSERIAL PRIMARY KEY,
 workspace_id BIGINT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
 user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 role TEXT NOT NULL CHECK (role IN ('owner','admin','editor','viewer')),
 granted_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
 created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
 UNIQUE (workspace_id,user_id)
);
CREATE INDEX IF NOT EXISTS idx_workspace_members_user ON workspace_members(user_id,workspace_id);
CREATE TABLE IF NOT EXISTS sandbox_execution_records (
 id TEXT PRIMARY KEY,
 user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 workspace_id BIGINT REFERENCES workspaces(id) ON DELETE SET NULL,
 status TEXT NOT NULL CHECK (status IN ('rejected','queued','running','succeeded','failed','timed_out')),
 image TEXT,
 command_name TEXT NOT NULL,
 exit_code INTEGER,
 result_json TEXT NOT NULL DEFAULT '{}',
 error_code TEXT,
 started_at TIMESTAMPTZ,
 completed_at TIMESTAMPTZ,
 created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_sandbox_runs_owner ON sandbox_execution_records(user_id,created_at DESC);
CREATE TABLE IF NOT EXISTS social_publish_jobs (
 id TEXT PRIMARY KEY,
 user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 content_id BIGINT NOT NULL REFERENCES social_content(id) ON DELETE CASCADE,
 platform TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'scheduled' CHECK (status IN ('scheduled','queued','blocked','publishing','published','failed','cancelled')),
 scheduled_at TIMESTAMPTZ NOT NULL,
 idempotency_key TEXT NOT NULL,
 external_post_id TEXT,
 last_error_code TEXT,
 created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
 UNIQUE (user_id,idempotency_key)
);
CREATE INDEX IF NOT EXISTS idx_social_publish_due ON social_publish_jobs(status,scheduled_at);
CREATE INDEX IF NOT EXISTS idx_social_publish_owner ON social_publish_jobs(user_id,created_at DESC);
CREATE TABLE IF NOT EXISTS request_traces (
 id BIGSERIAL PRIMARY KEY,
 request_id TEXT NOT NULL,
 method TEXT NOT NULL,
 route TEXT NOT NULL,
 status_code INTEGER NOT NULL,
 duration_ms INTEGER NOT NULL CHECK (duration_ms >= 0),
 created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_request_traces_created ON request_traces(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_request_traces_status ON request_traces(status_code,created_at DESC);
