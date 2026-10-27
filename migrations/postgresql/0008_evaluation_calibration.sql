-- Human-labelled evaluation outcomes enable measured calibration; raw deterministic
-- scores are not presented as calibrated reliability until enough labels exist.
ALTER TABLE agent_evaluations
    ADD COLUMN IF NOT EXISTS labelled_outcome REAL CHECK(labelled_outcome IS NULL OR (labelled_outcome >= 0 AND labelled_outcome <= 1));
ALTER TABLE agent_evaluations
    ADD COLUMN IF NOT EXISTS labelled_at TEXT;
ALTER TABLE agent_evaluations
    ADD COLUMN IF NOT EXISTS label_note TEXT;
CREATE INDEX IF NOT EXISTS idx_agent_evaluations_labelled
    ON agent_evaluations(user_id, labelled_at DESC) WHERE labelled_outcome IS NOT NULL;
