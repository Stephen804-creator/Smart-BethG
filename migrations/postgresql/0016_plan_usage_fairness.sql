-- Atomic per-plan request fairness counters. Backfill is not required: the first
-- admission seeds the counter from today's reservations, then increments under
-- a row-level upsert condition to prevent concurrent requests exceeding a plan.
CREATE TABLE IF NOT EXISTS plan_usage_counters (
 period_start DATE NOT NULL,
 user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 requests INTEGER NOT NULL CHECK (requests >= 0),
 updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
 PRIMARY KEY(period_start,user_id)
);
