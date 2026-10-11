-- SniperMemory v1: indexed retrieval over durable user-scoped records.
-- Added 2026-10-11. Queries still apply explicit owner/scope filters; full-text
-- indexes improve candidate lookup but do not replace authorization predicates.
CREATE INDEX IF NOT EXISTS idx_messages_conversation_id_desc
    ON messages (conversation_id, id DESC);

CREATE INDEX IF NOT EXISTS idx_messages_content_fts
    ON messages USING GIN (to_tsvector('simple', content));

CREATE INDEX IF NOT EXISTS idx_memory_owner_scope_ref_id
    ON memory (user_id, scope, scope_ref, id DESC);

CREATE INDEX IF NOT EXISTS idx_memory_content_fts
    ON memory USING GIN (to_tsvector('simple', content));

CREATE INDEX IF NOT EXISTS idx_knowledge_owner_workspace_id
    ON knowledge_chunks (user_id, workspace, id DESC);

CREATE INDEX IF NOT EXISTS idx_knowledge_content_fts
    ON knowledge_chunks USING GIN (to_tsvector('simple', content));
