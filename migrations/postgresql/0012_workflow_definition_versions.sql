-- Immutable workflow definition snapshots and run pinning.
-- Historical runs remain readable with a NULL snapshot reference; only newly
-- published/running definitions are pinned. Existing migrations are untouched.

CREATE TABLE IF NOT EXISTS workflow_definition_versions (
    id BIGSERIAL PRIMARY KEY,
    workflow_id INTEGER NOT NULL REFERENCES workflows(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    version INTEGER NOT NULL CHECK (version > 0),
    definition_format TEXT NOT NULL CHECK (definition_format IN ('legacy_steps', 'graph_v1')),
    definition_json TEXT NOT NULL,
    graph_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP::text),
    created_by INTEGER NOT NULL REFERENCES users(id),
    UNIQUE (workflow_id, version),
    UNIQUE (id, workflow_id)
);

ALTER TABLE workflows
    ADD COLUMN IF NOT EXISTS published_version INTEGER;

ALTER TABLE workflows
    ADD CONSTRAINT fk_workflows_published_definition
    FOREIGN KEY (id, published_version)
    REFERENCES workflow_definition_versions(workflow_id, version)
    DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE workflow_runs
    ADD COLUMN IF NOT EXISTS workflow_version_id BIGINT;

ALTER TABLE workflow_runs
    ADD CONSTRAINT fk_workflow_runs_definition_version
    FOREIGN KEY (workflow_version_id, workflow_id)
    REFERENCES workflow_definition_versions(id, workflow_id)
    ON DELETE RESTRICT;

CREATE INDEX IF NOT EXISTS idx_workflow_definition_versions_owner
    ON workflow_definition_versions(user_id, workflow_id, version DESC);

CREATE INDEX IF NOT EXISTS idx_workflow_runs_definition_version
    ON workflow_runs(workflow_version_id)
    WHERE workflow_version_id IS NOT NULL;
