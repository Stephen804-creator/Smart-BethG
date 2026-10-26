-- Units 16–20: organizations/workspaces, sandbox execution, publishing lifecycle, and operational telemetry.
CREATE TABLE IF NOT EXISTS organizations (
 id BIGSERIAL PRIMARY KEY,
 name TEXT NOT NULL,
 slug TEXT NOT NULL UNIQUE,
 owner_user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','suspended','archived')),
 created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS organization_members (
 organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
 user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 role TEXT NOT NULL CHECK(role IN ('owner','admin','member')),
 added_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
 created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
 PRIMARY KEY(organization_id,user_id)
);
CREATE INDEX IF NOT EXISTS idx_org_members_user ON organization_members(user_id, organization_id);
CREATE TABLE IF NOT EXISTS workspaces (
 id BIGSERIAL PRIMARY KEY,
 organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
 name TEXT NOT NULL,
 slug TEXT NOT NULL,
 description TEXT NOT NULL DEFAULT '',
 created_by INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','archived')),
 created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
 UNIQUE(organization_id,slug)
);
CREATE INDEX IF NOT EXISTS idx_workspaces_org ON workspaces(organization_id,status);
CREATE TABLE IF NOT EXISTS workspace_members (
 workspace_id BIGINT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
 user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 role TEXT NOT NULL CHECK(role IN ('admin','editor','viewer')),
 granted_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
 created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
 PRIMARY KEY(workspace_id,user_id)
);
CREATE INDEX IF NOT EXISTS idx_workspace_members_user ON workspace_members(user_id,workspace_id);
CREATE TABLE IF NOT EXISTS workspace_documents (
 id BIGSERIAL PRIMARY KEY,
 workspace_id BIGINT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
 created_by INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 title TEXT NOT NULL,
 body TEXT NOT NULL,
 version INTEGER NOT NULL DEFAULT 1,
 status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','archived')),
 created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_workspace_documents_scope ON workspace_documents(workspace_id,status,updated_at DESC);
CREATE TABLE IF NOT EXISTS sandbox_executions (
 id BIGSERIAL PRIMARY KEY,
 user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 language TEXT NOT NULL,
 source_sha256 TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('succeeded','failed','timed_out','unavailable')),
 exit_code INTEGER,
 stdout TEXT NOT NULL DEFAULT '',
 stderr TEXT NOT NULL DEFAULT '',
 duration_ms INTEGER NOT NULL DEFAULT 0,
 created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_sandbox_execution_owner ON sandbox_executions(user_id,created_at DESC);
CREATE TABLE IF NOT EXISTS social_publication_attempts (
 id BIGSERIAL PRIMARY KEY,
 social_content_id INTEGER NOT NULL REFERENCES social_content(id) ON DELETE CASCADE,
 user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 platform TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('approval_required','queued','publishing','published','failed','cancelled')),
 idempotency_key TEXT NOT NULL,
 approval_id TEXT,
 external_post_id TEXT,
 result_json TEXT NOT NULL DEFAULT '{}',
 error_code TEXT,
 created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
 UNIQUE(user_id,idempotency_key)
);
CREATE INDEX IF NOT EXISTS idx_social_publications_owner ON social_publication_attempts(user_id,created_at DESC);
CREATE TABLE IF NOT EXISTS operational_events (
 id BIGSERIAL PRIMARY KEY,
 request_id TEXT,
 event_type TEXT NOT NULL,
 severity TEXT NOT NULL DEFAULT 'info' CHECK(severity IN ('debug','info','warning','error','critical')),
 route_template TEXT,
 status_code INTEGER,
 duration_ms INTEGER,
 metadata_json TEXT NOT NULL DEFAULT '{}',
 created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_operational_events_created ON operational_events(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_operational_events_type_created ON operational_events(event_type,created_at DESC);
