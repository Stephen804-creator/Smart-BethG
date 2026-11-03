"""Owner-scoped persistence and hash chaining for provenance events."""
from repositories.provenance_contracts import canonical_json, sha256_hex


class ProvenanceRepository:
    def append_event(
        self, user_id, artifact_id, event_type, actor_type, payload=None,
        actor_id=None, actor_label=None, provider=None, model=None,
        agent_id=None, workflow_id=None, mission_id=None, idempotency_key=None,
    ):
        payload = payload or {}
        if idempotency_key is not None:
            idempotency_key = str(idempotency_key).strip()
            if not idempotency_key or len(idempotency_key) > 200:
                raise ValueError("Idempotency key must be between 1 and 200 characters.")

        conn = self._connection()
        try:
            artifact = conn.execute(
                "SELECT id FROM artifacts WHERE id=? AND user_id=? FOR UPDATE",
                (artifact_id, user_id),
            ).fetchone()
            if not artifact:
                raise ValueError("Artifact not found for this user.")

            if idempotency_key:
                existing = conn.execute(
                    "SELECT id, artifact_id FROM provenance_events "
                    "WHERE user_id=? AND idempotency_key=? LIMIT 1",
                    (user_id, idempotency_key),
                ).fetchone()
                if existing:
                    if existing["artifact_id"] != artifact_id:
                        raise ValueError("Idempotency key is already used for another artifact.")
                    conn.commit()
                    return self.get_event(user_id, existing["id"])

            previous = conn.execute(
                "SELECT sequence_number, event_sha256 FROM provenance_events "
                "WHERE artifact_id=? AND user_id=? ORDER BY sequence_number DESC LIMIT 1",
                (artifact_id, user_id),
            ).fetchone()
            sequence = (previous["sequence_number"] + 1) if previous else 1
            previous_digest = previous["event_sha256"] if previous else None
            event_body = {
                "event_type": event_type,
                "actor_type": actor_type,
                "actor_id": actor_id,
                "actor_label": actor_label,
                "provider": provider,
                "model": model,
                "agent_id": agent_id,
                "workflow_id": workflow_id,
                "mission_id": mission_id,
                "payload": payload,
            }
            payload_json = canonical_json(event_body)
            payload_digest = sha256_hex(payload_json)
            chain_body = {
                "artifact_id": artifact_id,
                "sequence_number": sequence,
                "payload_sha256": payload_digest,
                "previous_event_sha256": previous_digest,
            }
            event_digest = sha256_hex(canonical_json(chain_body))
            cursor = conn.execute(
                "INSERT INTO provenance_events("
                "user_id, artifact_id, sequence_number, event_type, actor_type, actor_id, actor_label, "
                "provider, model, agent_id, workflow_id, mission_id, payload_json, payload_sha256, "
                "previous_event_sha256, event_sha256, idempotency_key"
                ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) RETURNING id",
                (
                    user_id, artifact_id, sequence, event_type, actor_type, actor_id, actor_label,
                    provider, model, agent_id, workflow_id, mission_id, payload_json, payload_digest,
                    previous_digest, event_digest, idempotency_key,
                ),
            )
            event_id = cursor.fetchone()["id"]
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        return self.get_event(user_id, event_id)

    def list_events(self, user_id, artifact_id):
        conn = self._connection()
        try:
            rows = conn.execute(
                "SELECT * FROM provenance_events WHERE user_id=? AND artifact_id=? "
                "ORDER BY sequence_number ASC",
                (user_id, artifact_id),
            ).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def get_event(self, user_id, event_id):
        conn = self._connection()
        try:
            row = conn.execute(
                "SELECT * FROM provenance_events WHERE user_id=? AND id=? LIMIT 1",
                (user_id, event_id),
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    @staticmethod
    def _connection():
        from database import get_connection
        return get_connection()
