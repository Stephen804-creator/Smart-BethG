-- Asset Provenance and Attribution (APA).
-- New additive migration; never rewrite an already-applied migration.

CREATE UNIQUE INDEX IF NOT EXISTS idx_artifacts_id_user
    ON artifacts(id, user_id);

CREATE TABLE IF NOT EXISTS provenance_events (
    id BIGSERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    artifact_id INTEGER NOT NULL,
    sequence_number BIGINT NOT NULL CHECK (sequence_number > 0),
    event_type TEXT NOT NULL CHECK (event_type IN (
        'asset_created', 'asset_uploaded', 'source_attached',
        'ai_contribution', 'agent_contribution', 'human_edit',
        'transformation', 'review', 'approval', 'rejection',
        'manifest_generated', 'manifest_signed', 'verification',
        'export', 'deletion_requested'
    )),
    actor_type TEXT NOT NULL CHECK (actor_type IN (
        'human', 'smart_bethg', 'provider', 'external_tool', 'system', 'unknown'
    )),
    actor_id TEXT,
    actor_label TEXT,
    provider TEXT,
    model TEXT,
    agent_id TEXT,
    workflow_id BIGINT,
    mission_id INTEGER,
    payload_json TEXT NOT NULL DEFAULT '{}',
    payload_sha256 TEXT NOT NULL CHECK (payload_sha256 ~ '^[0-9a-f]{64}$'),
    previous_event_sha256 TEXT CHECK (
        previous_event_sha256 IS NULL OR previous_event_sha256 ~ '^[0-9a-f]{64}$'
    ),
    event_sha256 TEXT NOT NULL CHECK (event_sha256 ~ '^[0-9a-f]{64}$'),
    idempotency_key TEXT,
    created_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP::text),
    CONSTRAINT fk_provenance_event_artifact_owner
        FOREIGN KEY (artifact_id, user_id)
        REFERENCES artifacts(id, user_id) ON DELETE CASCADE,
    CONSTRAINT uq_provenance_event_sequence
        UNIQUE (artifact_id, sequence_number)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_provenance_event_owner_idempotency
    ON provenance_events(user_id, idempotency_key)
    WHERE idempotency_key IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_provenance_events_owner_artifact
    ON provenance_events(user_id, artifact_id, sequence_number);
CREATE INDEX IF NOT EXISTS idx_provenance_events_owner_created
    ON provenance_events(user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS provenance_manifests (
    id BIGSERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    artifact_id INTEGER NOT NULL,
    manifest_version INTEGER NOT NULL CHECK (manifest_version > 0),
    schema_id TEXT NOT NULL,
    manifest_json TEXT NOT NULL,
    manifest_sha256 TEXT NOT NULL CHECK (manifest_sha256 ~ '^[0-9a-f]{64}$'),
    event_chain_head_sha256 TEXT CHECK (
        event_chain_head_sha256 IS NULL OR event_chain_head_sha256 ~ '^[0-9a-f]{64}$'
    ),
    status TEXT NOT NULL DEFAULT 'unsigned' CHECK (
        status IN ('unsigned', 'signed', 'invalidated')
    ),
    created_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP::text),
    CONSTRAINT fk_provenance_manifest_artifact_owner
        FOREIGN KEY (artifact_id, user_id)
        REFERENCES artifacts(id, user_id) ON DELETE CASCADE,
    CONSTRAINT uq_provenance_manifest_version
        UNIQUE (artifact_id, manifest_version),
    CONSTRAINT uq_provenance_manifest_id_owner
        UNIQUE (id, user_id)
);
CREATE INDEX IF NOT EXISTS idx_provenance_manifests_owner_artifact
    ON provenance_manifests(user_id, artifact_id, manifest_version DESC);

CREATE TABLE IF NOT EXISTS provenance_signatures (
    id BIGSERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    manifest_id BIGINT NOT NULL,
    algorithm TEXT NOT NULL CHECK (algorithm = 'Ed25519'),
    key_id TEXT NOT NULL CHECK (length(key_id) BETWEEN 1 AND 128),
    signature_base64 TEXT NOT NULL,
    public_key_base64 TEXT NOT NULL,
    trust_level TEXT NOT NULL CHECK (
        trust_level IN ('development', 'configured', 'external_certificate')
    ),
    signed_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP::text),
    CONSTRAINT fk_provenance_signature_manifest_owner
        FOREIGN KEY (manifest_id, user_id)
        REFERENCES provenance_manifests(id, user_id) ON DELETE CASCADE,
    CONSTRAINT uq_provenance_signature_manifest_key
        UNIQUE (manifest_id, key_id)
);
CREATE INDEX IF NOT EXISTS idx_provenance_signatures_owner_manifest
    ON provenance_signatures(user_id, manifest_id);
