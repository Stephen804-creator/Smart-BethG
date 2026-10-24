-- Add typed memory, provenance, confidence and lifecycle metadata without
-- rewriting the immutable baseline migration. Existing rows remain usable.
ALTER TABLE memory ADD COLUMN IF NOT EXISTS memory_type TEXT NOT NULL DEFAULT 'episodic';
ALTER TABLE memory ADD COLUMN IF NOT EXISTS confidence REAL NOT NULL DEFAULT 1.0;
ALTER TABLE memory ADD COLUMN IF NOT EXISTS source_ref TEXT;
ALTER TABLE memory ADD COLUMN IF NOT EXISTS metadata_json TEXT NOT NULL DEFAULT '{}';
ALTER TABLE memory ADD COLUMN IF NOT EXISTS expires_at TEXT;
ALTER TABLE memory ADD COLUMN IF NOT EXISTS updated_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP::text);

CREATE INDEX IF NOT EXISTS idx_memory_user_scope_updated
    ON memory(user_id, scope, updated_at DESC, id DESC);
CREATE INDEX IF NOT EXISTS idx_memory_user_type
    ON memory(user_id, memory_type);
