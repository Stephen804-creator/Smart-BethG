-- Stable idempotency keys make internal workflow adapters safe to replay
-- after a worker crash between the service write and step completion.
ALTER TABLE research ADD COLUMN IF NOT EXISTS idempotency_key TEXT;
ALTER TABLE artifacts ADD COLUMN IF NOT EXISTS idempotency_key TEXT;
ALTER TABLE social_content ADD COLUMN IF NOT EXISTS idempotency_key TEXT;
CREATE UNIQUE INDEX IF NOT EXISTS idx_research_owner_idempotency
    ON research(user_id, idempotency_key) WHERE idempotency_key IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_artifacts_owner_idempotency
    ON artifacts(user_id, idempotency_key) WHERE idempotency_key IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_social_content_owner_idempotency
    ON social_content(user_id, idempotency_key) WHERE idempotency_key IS NOT NULL;
