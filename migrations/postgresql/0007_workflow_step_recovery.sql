-- Durable per-step workflow ledger. Unique (run, step) makes replay recover the
-- same child mission instead of dispatching a duplicate after worker restart.
CREATE TABLE IF NOT EXISTS workflow_step_runs (
 id BIGSERIAL PRIMARY KEY,
 workflow_run_id BIGINT NOT NULL REFERENCES workflow_runs(id) ON DELETE CASCADE,
 user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 step_index INTEGER NOT NULL CHECK(step_index >= 0),
 step_id TEXT NOT NULL,
 step_type TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'created' CHECK(status IN ('created','running','waiting','completed','failed')),
 mission_id INTEGER REFERENCES missions(id) ON DELETE SET NULL,
 result_json TEXT NOT NULL DEFAULT '{}',
 error TEXT,
 created_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP::text),
 updated_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP::text),
 completed_at TEXT,
 UNIQUE(workflow_run_id, step_index)
);
CREATE INDEX IF NOT EXISTS idx_workflow_step_runs_owner ON workflow_step_runs(user_id, workflow_run_id, step_index);
CREATE INDEX IF NOT EXISTS idx_workflow_step_runs_mission ON workflow_step_runs(mission_id) WHERE mission_id IS NOT NULL;
