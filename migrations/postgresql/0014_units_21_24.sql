-- Units 21-24: durable schedules, declarative extensions, usage intelligence, and commercial entitlements.
CREATE TABLE IF NOT EXISTS scheduled_agent_jobs (
 id BIGSERIAL PRIMARY KEY,
 user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 name TEXT NOT NULL CHECK (length(trim(name)) BETWEEN 1 AND 120),
 workflow_id BIGINT NOT NULL REFERENCES workflows(id) ON DELETE CASCADE,
 scheduled_at TIMESTAMPTZ NOT NULL,
 interval_seconds INTEGER CHECK (interval_seconds IS NULL OR interval_seconds BETWEEN 60 AND 2592000),
 status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','paused','completed','cancelled')),
 next_run_at TIMESTAMPTZ NOT NULL,
 last_run_at TIMESTAMPTZ,
 run_count INTEGER NOT NULL DEFAULT 0 CHECK (run_count >= 0),
 max_runs INTEGER CHECK (max_runs IS NULL OR max_runs BETWEEN 1 AND 10000),
 created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_scheduled_jobs_due ON scheduled_agent_jobs(status,next_run_at);
CREATE INDEX IF NOT EXISTS idx_scheduled_jobs_owner ON scheduled_agent_jobs(user_id,created_at DESC);
CREATE TABLE IF NOT EXISTS scheduled_job_runs (
 id BIGSERIAL PRIMARY KEY,
 scheduled_job_id BIGINT NOT NULL REFERENCES scheduled_agent_jobs(id) ON DELETE CASCADE,
 user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 scheduled_for TIMESTAMPTZ NOT NULL,
 workflow_run_id BIGINT REFERENCES workflow_runs(id) ON DELETE SET NULL,
 status TEXT NOT NULL DEFAULT 'dispatching' CHECK (status IN ('dispatching','dispatched','failed')),
 error_code TEXT,
 created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
 UNIQUE(scheduled_job_id,scheduled_for)
);
CREATE INDEX IF NOT EXISTS idx_scheduled_job_runs_owner ON scheduled_job_runs(user_id,created_at DESC);
CREATE TABLE IF NOT EXISTS extension_manifests (
 id BIGSERIAL PRIMARY KEY,
 owner_user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 extension_key TEXT NOT NULL CHECK (extension_key ~ '^[a-z][a-z0-9_-]{1,62}$'),
 version TEXT NOT NULL CHECK (length(version) BETWEEN 1 AND 40),
 manifest_json TEXT NOT NULL CHECK (length(manifest_json) <= 50000),
 status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','approved','disabled')),
 created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
 UNIQUE(owner_user_id,extension_key,version)
);
CREATE INDEX IF NOT EXISTS idx_extension_manifests_owner ON extension_manifests(owner_user_id,status);
CREATE TABLE IF NOT EXISTS account_plan_assignments (
 user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
 plan_key TEXT NOT NULL DEFAULT 'free' CHECK (plan_key IN ('free','starter','pro','team')),
 status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','past_due','cancelled','suspended')),
 effective_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS credit_ledger (
 id BIGSERIAL PRIMARY KEY,
 user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 delta_credits BIGINT NOT NULL CHECK (delta_credits <> 0),
 reason TEXT NOT NULL CHECK (length(trim(reason)) BETWEEN 1 AND 120),
 source TEXT NOT NULL CHECK (source IN ('plan_allocation','admin_grant','approved_reward','usage_debit','refund','adjustment')),
 idempotency_key TEXT NOT NULL CHECK (length(idempotency_key) BETWEEN 1 AND 200),
 metadata_json TEXT NOT NULL DEFAULT '{}',
 created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
 UNIQUE(user_id,idempotency_key)
);
CREATE INDEX IF NOT EXISTS idx_credit_ledger_owner ON credit_ledger(user_id,created_at DESC);
CREATE TABLE IF NOT EXISTS reward_events (
 id BIGSERIAL PRIMARY KEY,
 user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 reward_key TEXT NOT NULL CHECK (reward_key ~ '^[a-z][a-z0-9_-]{1,62}$'),
 credits BIGINT NOT NULL CHECK (credits BETWEEN 1 AND 100000),
 status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','approved','rejected')),
 idempotency_key TEXT NOT NULL CHECK (length(idempotency_key) BETWEEN 1 AND 200),
 reviewed_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
 reviewed_at TIMESTAMPTZ,
 created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
 UNIQUE(user_id,idempotency_key)
);
CREATE INDEX IF NOT EXISTS idx_reward_events_review ON reward_events(status,created_at);
