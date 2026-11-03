-- Preserve the actual Smart BethG orchestrator and fallback outcome
-- alongside each assistant message so later artifact creation can cite the
-- exact successful provider execution without retaining private prompts.
ALTER TABLE messages ADD COLUMN IF NOT EXISTS orchestrator_id TEXT;
ALTER TABLE messages ADD COLUMN IF NOT EXISTS fallback_used BOOLEAN NOT NULL DEFAULT FALSE;

CREATE INDEX IF NOT EXISTS idx_messages_conversation_provider_model
    ON messages(conversation_id, provider, model, id);
