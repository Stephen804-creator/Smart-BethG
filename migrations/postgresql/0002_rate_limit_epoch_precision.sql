-- Preserve sub-second precision for Unix epoch timestamps used by the
-- database-backed authentication limiter. PostgreSQL REAL has only about
-- 7 decimal digits of precision; at current epoch values it rounds in steps
-- of roughly 128 seconds, which can make a 60-second window appear empty.
ALTER TABLE auth_rate_limit_events
    ALTER COLUMN hit_epoch TYPE DOUBLE PRECISION
    USING hit_epoch::DOUBLE PRECISION;

-- Older deployments may not have this lock table because it was introduced
-- after the immutable baseline migration. Create it safely before using it.
CREATE TABLE IF NOT EXISTS auth_rate_limit_locks (
    key_hash TEXT PRIMARY KEY,
    last_seen_epoch DOUBLE PRECISION NOT NULL
);

ALTER TABLE auth_rate_limit_locks
    ALTER COLUMN last_seen_epoch TYPE DOUBLE PRECISION
    USING last_seen_epoch::DOUBLE PRECISION;

CREATE INDEX IF NOT EXISTS idx_auth_rate_limit_events_key_epoch
    ON auth_rate_limit_events (key_hash, hit_epoch);
