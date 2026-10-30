-- Unit B: immutable quarantine intake metadata. Quarantined uploads are not
-- regular files and cannot be extracted, indexed, summarized, or executed.
CREATE TABLE IF NOT EXISTS file_quarantine_records (
    id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    original_filename TEXT NOT NULL,
    object_locator TEXT NOT NULL,
    sha256 TEXT NOT NULL CHECK (sha256 ~ '^[0-9a-f]{64}$'),
    byte_size BIGINT NOT NULL CHECK (byte_size > 0),
    detected_media_type TEXT NOT NULL,
    declared_media_type TEXT,
    status TEXT NOT NULL DEFAULT 'quarantined'
        CHECK (status IN ('quarantined','rejected','released')),
    reason_code TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    reviewed_at TIMESTAMPTZ,
    released_file_id BIGINT REFERENCES files(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_file_quarantine_owner
    ON file_quarantine_records(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_file_quarantine_status
    ON file_quarantine_records(status, created_at DESC);
