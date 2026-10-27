-- Encrypted provider credentials and one-time OAuth state.
CREATE TABLE IF NOT EXISTS connector_credentials (
 installation_id BIGINT PRIMARY KEY REFERENCES connector_installations(id) ON DELETE CASCADE,
 encrypted_payload TEXT NOT NULL,
 provider_account TEXT,
 scopes_json TEXT NOT NULL DEFAULT '[]',
 expires_at TIMESTAMPTZ,
 created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS connector_oauth_states (
 state_hash TEXT PRIMARY KEY,
 user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 installation_id BIGINT NOT NULL REFERENCES connector_installations(id) ON DELETE CASCADE,
 connector_key TEXT NOT NULL,
 verifier TEXT,
 expires_at TIMESTAMPTZ NOT NULL,
 consumed_at TIMESTAMPTZ,
 created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_connector_oauth_states_expiry ON connector_oauth_states(expires_at);
