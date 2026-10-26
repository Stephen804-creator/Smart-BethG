CREATE TABLE IF NOT EXISTS worker_heartbeats (
 worker_id TEXT PRIMARY KEY,
 status TEXT NOT NULL CHECK(status IN ('starting','healthy','degraded','stopping')),
 last_seen TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
 details_json TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_worker_heartbeats_seen ON worker_heartbeats(last_seen DESC);
