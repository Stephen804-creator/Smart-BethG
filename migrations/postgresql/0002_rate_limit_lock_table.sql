-- Shared row-lock table for atomic rate limiting across PostgreSQL replicas.
-- Added 2026-10-10. Existing deployments receive this through the migration runner.
CREATE TABLE IF NOT EXISTS auth_rate_limit_locks (
    key_hash TEXT PRIMARY KEY,
    last_seen_epoch DOUBLE PRECISION NOT NULL
);
