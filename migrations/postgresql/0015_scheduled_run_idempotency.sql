-- Idempotent link from a recurring schedule occurrence to its workflow run.
ALTER TABLE workflow_runs
 ADD COLUMN IF NOT EXISTS scheduled_job_run_id BIGINT REFERENCES scheduled_job_runs(id) ON DELETE SET NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_workflow_runs_scheduled_job_run
 ON workflow_runs(scheduled_job_run_id) WHERE scheduled_job_run_id IS NOT NULL;
