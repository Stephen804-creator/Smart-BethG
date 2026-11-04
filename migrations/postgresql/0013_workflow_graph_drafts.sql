-- Store validated graph drafts directly, while retaining the legacy step
-- projection only where the graph can be executed by the current sequential
-- compatibility runtime. Existing workflows remain graph_json NULL.
ALTER TABLE workflows
    ADD COLUMN IF NOT EXISTS graph_json TEXT;
