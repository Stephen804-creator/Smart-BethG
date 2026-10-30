-- Durable file inspection state. The original bytes remain in private quarantine
-- storage until a worker verifies them and atomically releases a trusted file row.
ALTER TABLE file_quarantine_records
    ADD COLUMN IF NOT EXISTS inspection_status TEXT NOT NULL DEFAULT 'queued'
        CHECK (inspection_status IN ('queued','checking','clean','rejected','failed')),
    ADD COLUMN IF NOT EXISTS inspection_attempts INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS inspection_engine TEXT,
    ADD COLUMN IF NOT EXISTS inspected_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS inspection_error_code TEXT;

CREATE INDEX IF NOT EXISTS idx_file_quarantine_inspection
    ON file_quarantine_records(inspection_status, created_at);
