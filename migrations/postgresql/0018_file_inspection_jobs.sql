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

-- PDF parsing results are produced by the worker, never by an API request.
CREATE TABLE IF NOT EXISTS file_extractions (
    file_id INTEGER PRIMARY KEY REFERENCES files(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending','ready','failed')),
    extracted_text TEXT,
    page_count INTEGER,
    error_code TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (
        (status = 'ready' AND extracted_text IS NOT NULL)
        OR status <> 'ready'
    )
);
CREATE INDEX IF NOT EXISTS idx_file_extractions_owner
    ON file_extractions(user_id, status);

-- Existing PDF files are queued for background extraction so the API no longer
-- needs to parse historical documents in request workers.
INSERT INTO file_extractions(file_id,user_id,status)
SELECT id,user_id,'pending' FROM files
WHERE right(lower(filename),4) = '.pdf'
ON CONFLICT(file_id) DO NOTHING;

INSERT INTO background_jobs(
    id,user_id,job_type,payload_json,status,priority,idempotency_key,
    max_attempts,available_at
)
SELECT
    md5('file-pdf-extract:' || f.id::text),
    f.user_id,
    'file.extract_pdf',
    json_build_object('file_id',f.id)::text,
    'queued',
    1,
    'file-pdf-extract:' || f.id::text,
    3,
    to_char(CURRENT_TIMESTAMP AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US"+00:00"')
FROM files f
WHERE right(lower(f.filename),4) = '.pdf'
ON CONFLICT(user_id,idempotency_key) DO NOTHING;
