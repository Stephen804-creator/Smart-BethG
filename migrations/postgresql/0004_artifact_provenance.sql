-- Artifact provenance metadata for user-created, uploaded, campaign, and provider outputs.
-- Created 2026-10-10 UTC. Released migrations are immutable; use a new version for later changes.

ALTER TABLE artifacts ADD COLUMN IF NOT EXISTS source_type TEXT NOT NULL DEFAULT 'user_created';
ALTER TABLE artifacts ADD COLUMN IF NOT EXISTS source_id TEXT;
ALTER TABLE artifacts ADD COLUMN IF NOT EXISTS provider TEXT;
ALTER TABLE artifacts ADD COLUMN IF NOT EXISTS model TEXT;
ALTER TABLE artifacts ADD COLUMN IF NOT EXISTS metadata_json TEXT NOT NULL DEFAULT '{}';

CREATE INDEX IF NOT EXISTS idx_artifacts_owner_source
    ON artifacts(user_id, source_type, source_id);
