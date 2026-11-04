-- Store validated graph drafts directly, while retaining the legacy step
-- projection only where the graph can be executed by the current sequential
-- compatibility runtime. Existing workflows remain graph_json NULL.
ALTER TABLE workflows
    ADD COLUMN IF NOT EXISTS graph_json TEXT;

ALTER TABLE workflows
    ADD COLUMN IF NOT EXISTS definition_format TEXT NOT NULL DEFAULT 'legacy_steps';

ALTER TABLE workflows
    ADD CONSTRAINT chk_workflows_definition_format
    CHECK (definition_format IN ('legacy_steps', 'graph_v1'));
