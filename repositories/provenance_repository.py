"""Owner-scoped persistence and hash chaining for provenance events."""
import hmac
import json
from repositories.provenance_contracts import canonical_json, sha256_hex, validate_event


class ProvenanceRepository:
    def append_event(
        self, user_id, artifact_id, event_type, actor_type, payload=None,
        actor_id=None, actor_label=None, provider=None, model=None,
        agent_id=None, workflow_id=None, mission_id=None, idempotency_key=None,
    ):
        payload = validate_event(
            event_type, actor_type, payload, actor_id=actor_id, actor_label=actor_label
        )
        for label, value in (("provider", provider), ("model", model), ("agent_id", agent_id)):
            if value is not None and (not isinstance(value, str) or len(value) > 160):
                raise ValueError(f"Provenance {label} must be at most 160 characters.")
        for label, value in (("workflow_id", workflow_id), ("mission_id", mission_id)):
            if value is not None and (not isinstance(value, int) or isinstance(value, bool) or value < 1):
                raise ValueError(f"Provenance {label} must be a positive integer.")
        if idempotency_key is not None:
            idempotency_key = str(idempotency_key).strip()
            if not idempotency_key or len(idempotency_key) > 200:
                raise ValueError("Idempotency key must be between 1 and 200 characters.")

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
        payload_digest = sha256_hex(canonical_json(event_body))
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
                    "SELECT id, artifact_id, payload_sha256 FROM provenance_events "
                    "WHERE user_id=? AND idempotency_key=? LIMIT 1",
                    (user_id, idempotency_key),
                ).fetchone()
                if existing:
                    if existing["artifact_id"] != artifact_id:
                        raise ValueError("Idempotency key is already used for another artifact.")
                    if not hmac.compare_digest(existing["payload_sha256"], payload_digest):
                        raise ValueError("Idempotency key was already used for a different provenance event.")
                    conn.commit()
                    return self.get_event(user_id, existing["id"])

            previous = conn.execute(
                "SELECT sequence_number, event_sha256 FROM provenance_events "
                "WHERE artifact_id=? AND user_id=? ORDER BY sequence_number DESC LIMIT 1",
                (artifact_id, user_id),
            ).fetchone()
            sequence = (previous["sequence_number"] + 1) if previous else 1
            previous_digest = previous["event_sha256"] if previous else None
            payload_json = canonical_json(payload)
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

    def verify_chain(self, user_id, artifact_id):
        """Recompute every event digest and sequence link for one owner's artifact."""
        rows = self.list_events(user_id, artifact_id)
        previous_digest = None
        expected_sequence = 1
        for row in rows:
            if row["sequence_number"] != expected_sequence:
                return {
                    "valid": False, "events_checked": expected_sequence - 1,
                    "head_sha256": previous_digest, "reason": "sequence_gap",
                }
            try:
                payload = json.loads(row["payload_json"])
                event_body = {
                    "event_type": row["event_type"],
                    "actor_type": row["actor_type"],
                    "actor_id": row["actor_id"],
                    "actor_label": row["actor_label"],
                    "provider": row["provider"],
                    "model": row["model"],
                    "agent_id": row["agent_id"],
                    "workflow_id": row["workflow_id"],
                    "mission_id": row["mission_id"],
                    "payload": payload,
                }
                payload_digest = sha256_hex(canonical_json(event_body))
                chain_body = {
                    "artifact_id": row["artifact_id"],
                    "sequence_number": row["sequence_number"],
                    "payload_sha256": payload_digest,
                    "previous_event_sha256": previous_digest,
                }
                event_digest = sha256_hex(canonical_json(chain_body))
            except (TypeError, ValueError, KeyError):
                return {
                    "valid": False, "events_checked": expected_sequence - 1,
                    "head_sha256": previous_digest, "reason": "malformed_event",
                }
            if not hmac.compare_digest(str(row["payload_sha256"]), payload_digest):
                reason = "payload_digest_mismatch"
            elif row["previous_event_sha256"] != previous_digest:
                reason = "previous_digest_mismatch"
            elif not hmac.compare_digest(str(row["event_sha256"]), event_digest):
                reason = "event_digest_mismatch"
            else:
                reason = None
            if reason:
                return {
                    "valid": False, "events_checked": expected_sequence - 1,
                    "head_sha256": previous_digest, "reason": reason,
                }
            previous_digest = event_digest
            expected_sequence += 1
        return {
            "valid": True, "events_checked": len(rows),
            "head_sha256": previous_digest, "reason": None,
        }

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
