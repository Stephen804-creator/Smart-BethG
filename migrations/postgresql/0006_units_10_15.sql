-- Additive schema for workflow execution and Units 11–15 evidence/lifecycle foundations.
CREATE TABLE IF NOT EXISTS workflow_runs (
 id BIGSERIAL PRIMARY KEY, workflow_id BIGINT NOT NULL REFERENCES workflows(id) ON DELETE CASCADE,
 user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, workflow_version INTEGER NOT NULL,
 status TEXT NOT NULL DEFAULT 'queued' CHECK(status IN ('queued','running','waiting','completed','failed','cancelled')),
 current_step INTEGER NOT NULL DEFAULT 0, result_json TEXT NOT NULL DEFAULT '{}', error TEXT,
 started_at TEXT, completed_at TEXT, created_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP::text),
 updated_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP::text)
);
CREATE INDEX IF NOT EXISTS idx_workflow_runs_owner ON workflow_runs(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_workflow_runs_workflow ON workflow_runs(workflow_id, created_at DESC);
CREATE TABLE IF NOT EXISTS decision_ledger (
 id BIGSERIAL PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 mission_id INTEGER REFERENCES missions(id) ON DELETE SET NULL,
 workflow_run_id BIGINT REFERENCES workflow_runs(id) ON DELETE SET NULL,
 decision_type TEXT NOT NULL, decision_json TEXT NOT NULL, evidence_json TEXT NOT NULL DEFAULT '[]',
 outcome TEXT, created_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP::text)
);
CREATE INDEX IF NOT EXISTS idx_decision_ledger_owner ON decision_ledger(user_id, created_at DESC);
CREATE TABLE IF NOT EXISTS agent_team_runs (
 id BIGSERIAL PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 objective TEXT NOT NULL, assignments_json TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'planned' CHECK(status IN ('planned','running','completed','failed','cancelled')),
 created_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP::text), updated_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP::text)
);
CREATE TABLE IF NOT EXISTS agent_evaluations (
 id BIGSERIAL PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 subject_type TEXT NOT NULL, subject_id TEXT, rubric_version TEXT NOT NULL,
 score REAL NOT NULL CHECK(score >= 0 AND score <= 1), findings_json TEXT NOT NULL,
 evaluator_type TEXT NOT NULL DEFAULT 'deterministic', created_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP::text)
);
CREATE INDEX IF NOT EXISTS idx_agent_evaluations_owner ON agent_evaluations(user_id, created_at DESC);
CREATE TABLE IF NOT EXISTS account_lifecycle_requests (
 id BIGSERIAL PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 request_type TEXT NOT NULL CHECK(request_type IN ('data_export','account_deletion')),
 status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','processing','completed','rejected','cancelled')),
 details_json TEXT NOT NULL DEFAULT '{}', created_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP::text),
 updated_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP::text)
);
CREATE INDEX IF NOT EXISTS idx_account_lifecycle_owner ON account_lifecycle_requests(user_id, created_at DESC);
