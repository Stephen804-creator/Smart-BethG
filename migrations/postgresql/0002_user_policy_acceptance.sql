-- Smart BethG PostgreSQL migration: versioned legal consent tracking.
-- This is intentionally additive. It preserves the original schema and adds
-- audited acceptance records for terms, privacy policy, and minimum-age checks.

CREATE TABLE IF NOT EXISTS user_policy_acceptance(
    user_id INTEGER PRIMARY KEY,
    accepted_terms_version TEXT NOT NULL,
    accepted_privacy_version TEXT NOT NULL,
    age_verified BOOLEAN NOT NULL DEFAULT FALSE,
    accepted_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_user_policy_acceptance_user
        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_user_policy_acceptance_user_id
    ON user_policy_acceptance(user_id);

CREATE INDEX IF NOT EXISTS idx_user_policy_acceptance_version
    ON user_policy_acceptance(accepted_terms_version, accepted_privacy_version);

