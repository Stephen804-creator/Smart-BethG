-- Additive connector, queue, and mission execution schema.
CREATE TABLE IF NOT EXISTS connector_installations (
 id BIGSERIAL PRIMARY KEY,
 user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 connector_key TEXT NOT NULL,
 label TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'disconnected' CHECK(status IN ('disconnected','connected','error','revoked')),
 credential_ref TEXT,
 granted_permissions_json TEXT NOT NULL DEFAULT '[]',
 created_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP::text),
 updated_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP::text),
 UNIQUE(user_id, connector_key, label)
);
CREATE INDEX IF NOT EXISTS idx_connector_installations_owner ON connector_installations(user_id, updated_at);
CREATE TABLE IF NOT EXISTS background_jobs (
 id TEXT PRIMARY KEY,
 user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 job_type TEXT NOT NULL,
 payload_json TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'queued' CHECK(status IN ('queued','running','succeeded','failed','cancelled')),
 priority INTEGER NOT NULL DEFAULT 0,
 idempotency_key TEXT NOT NULL,
 attempts INTEGER NOT NULL DEFAULT 0,
 max_attempts INTEGER NOT NULL DEFAULT 5,
 available_at TEXT NOT NULL,
 started_at TEXT,
 completed_at TEXT,
 lease_until TEXT,
 lease_token TEXT,
 last_error TEXT,
 result_json TEXT,
 created_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP::text),
 updated_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP::text),
 UNIQUE(user_id, idempotency_key)
);
CREATE INDEX IF NOT EXISTS idx_background_jobs_claim ON background_jobs(status, available_at, priority DESC, created_at);
CREATE INDEX IF NOT EXISTS idx_background_jobs_owner ON background_jobs(user_id, created_at DESC);
ALTER TABLE missions ADD COLUMN IF NOT EXISTS plan_json TEXT NOT NULL DEFAULT '[]';
CREATE INDEX IF NOT EXISTS idx_mission_runs_mission_attempt ON mission_runs(mission_id, attempt_number DESC);
