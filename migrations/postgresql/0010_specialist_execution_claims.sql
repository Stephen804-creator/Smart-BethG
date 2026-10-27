-- Guard specialist orchestration against concurrent duplicate worker claims.
ALTER TABLE agent_team_runs
    ADD COLUMN IF NOT EXISTS execution_claim_token TEXT;
ALTER TABLE agent_team_runs
    ADD COLUMN IF NOT EXISTS execution_claimed_at TIMESTAMPTZ;
CREATE INDEX IF NOT EXISTS idx_agent_team_claim
    ON agent_team_runs(status, execution_claimed_at);
