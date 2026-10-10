-- Smart BethG social campaigns, account connections, and durable publishing queue.
-- Created 2026-10-10 UTC. Never edit after release; use the next numbered migration.

ALTER TABLE social_content ADD COLUMN IF NOT EXISTS campaign_id INTEGER;
ALTER TABLE social_content ADD COLUMN IF NOT EXISTS scheduled_at TEXT;

CREATE TABLE IF NOT EXISTS social_campaigns (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    objective TEXT NOT NULL,
    platforms_json TEXT NOT NULL,
    timezone TEXT NOT NULL,
    start_at TEXT NOT NULL,
    end_at TEXT,
    cadence_json TEXT NOT NULL DEFAULT '{}',
    autonomy_mode TEXT NOT NULL DEFAULT 'review_each_post',
    autopublish_authorized_at TIMESTAMPTZ,
    authorization_scope_json TEXT,
    daily_post_limit INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'draft',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

ALTER TABLE social_campaigns ADD COLUMN IF NOT EXISTS audience TEXT NOT NULL DEFAULT '';
ALTER TABLE social_campaigns ADD COLUMN IF NOT EXISTS tone TEXT NOT NULL DEFAULT 'clear, helpful';
ALTER TABLE social_campaigns ADD COLUMN IF NOT EXISTS reference_urls_json TEXT NOT NULL DEFAULT '[]';
ALTER TABLE social_campaigns ADD COLUMN IF NOT EXISTS content_rules TEXT NOT NULL DEFAULT '';

CREATE INDEX IF NOT EXISTS idx_social_campaigns_owner_updated
    ON social_campaigns(user_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS social_connections (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    platform TEXT NOT NULL,
    external_account_id TEXT NOT NULL,
    display_name TEXT,
    credential_ref TEXT NOT NULL,
    scopes_json TEXT NOT NULL DEFAULT '[]',
    status TEXT NOT NULL DEFAULT 'pending',
    connected_at TIMESTAMPTZ,
    last_validated_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, platform, external_account_id)
);

CREATE INDEX IF NOT EXISTS idx_social_connections_owner_platform
    ON social_connections(user_id, platform, status);

CREATE TABLE IF NOT EXISTS social_publish_jobs (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    campaign_id INTEGER,
    content_id INTEGER NOT NULL,
    connection_id INTEGER,
    platform TEXT NOT NULL,
    scheduled_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued',
    idempotency_key TEXT NOT NULL UNIQUE,
    attempts INTEGER NOT NULL DEFAULT 0,
    lease_until TEXT,
    error_code TEXT,
    error_message TEXT,
    external_post_id TEXT,
    published_at TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_social_publish_jobs_due
    ON social_publish_jobs(status, scheduled_at, id);

CREATE INDEX IF NOT EXISTS idx_social_publish_jobs_owner
    ON social_publish_jobs(user_id, created_at DESC);
