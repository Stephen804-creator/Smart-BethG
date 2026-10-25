-- Conditional workflow steps can explicitly skip downstream work.
ALTER TABLE workflow_step_runs DROP CONSTRAINT IF EXISTS workflow_step_runs_status_check;
ALTER TABLE workflow_step_runs ADD CONSTRAINT workflow_step_runs_status_check
    CHECK(status IN ('created','running','waiting','completed','failed','skipped'));
