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

    def verify_chain(self, user_id, artifact_id, expected_head=None):
        """Recompute the full chain or verify a specific historical chain prefix."""
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
            if expected_head is not None and expected_head != "" and hmac.compare_digest(event_digest, str(expected_head)):
                return {
                    "valid": True, "events_checked": expected_sequence,
                    "head_sha256": previous_digest, "reason": None,
                }
            expected_sequence += 1
        if expected_head is not None:
            if expected_head == "" and not rows:
                return {
                    "valid": True, "events_checked": 0,
                    "head_sha256": None, "reason": None,
                }
            return {
                "valid": False, "events_checked": len(rows),
                "head_sha256": previous_digest, "reason": "expected_head_not_found",
            }
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

    def get_latest_manifest(self, user_id, artifact_id):
        conn = self._connection()
        try:
            row = conn.execute(
                "SELECT * FROM provenance_manifests WHERE user_id=? AND artifact_id=? "
                "ORDER BY manifest_version DESC LIMIT 1",
                (user_id, artifact_id),
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def get_manifest(self, user_id, artifact_id, manifest_id):
        conn = self._connection()
        try:
            row = conn.execute(
                "SELECT * FROM provenance_manifests "
                "WHERE user_id=? AND artifact_id=? AND id=? LIMIT 1",
                (user_id, artifact_id, manifest_id),
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def list_signatures(self, user_id, manifest_id):
        conn = self._connection()
        try:
            rows = conn.execute(
                "SELECT * FROM provenance_signatures "
                "WHERE user_id=? AND manifest_id=? ORDER BY signed_at ASC, id ASC",
                (user_id, manifest_id),
            ).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def save_manifest(
        self, user_id, artifact_id, schema_id, manifest_json, manifest_sha256,
        event_chain_head_sha256, signature=None,
    ):
        """Append a deterministic manifest version and optional signature atomically."""
        if not isinstance(manifest_json, str) or len(manifest_json.encode("utf-8")) > 256 * 1024:
            raise ValueError("Provenance manifest exceeds the 256 KiB limit.")
        conn = self._connection()
        try:
            artifact = conn.execute(
                "SELECT id FROM artifacts WHERE id=? AND user_id=? FOR UPDATE",
                (artifact_id, user_id),
            ).fetchone()
            if not artifact:
                raise ValueError("Artifact not found for this user.")
            existing = conn.execute(
                "SELECT * FROM provenance_manifests WHERE user_id=? AND artifact_id=? "
                "AND manifest_sha256=? AND event_chain_head_sha256 IS NOT DISTINCT FROM ? "
                "ORDER BY manifest_version DESC LIMIT 1",
                (user_id, artifact_id, manifest_sha256, event_chain_head_sha256),
            ).fetchone()
            if existing:
                manifest_id = existing["id"]
                if signature:
                    saved = conn.execute(
                        "SELECT * FROM provenance_signatures WHERE user_id=? AND manifest_id=? AND key_id=? LIMIT 1",
                        (user_id, manifest_id, signature["key_id"]),
                    ).fetchone()
                    if saved:
                        if (
                            saved["signature_base64"] != signature["signature_base64"]
                            or saved["public_key_base64"] != signature["public_key_base64"]
                            or saved["trust_level"] != signature["trust_level"]
                        ):
                            raise ValueError("A different signature already exists for this manifest and key ID.")
                    else:
                        conn.execute(
                            "INSERT INTO provenance_signatures("
                            "user_id, manifest_id, algorithm, key_id, signature_base64, public_key_base64, trust_level"
                            ") VALUES (?, ?, ?, ?, ?, ?, ?)",
                            (
                                user_id, manifest_id, signature["algorithm"], signature["key_id"],
                                signature["signature_base64"], signature["public_key_base64"],
                                signature["trust_level"],
                            ),
                        )
                        conn.execute(
                            "UPDATE provenance_manifests SET status='signed' WHERE id=? AND user_id=?",
                            (manifest_id, user_id),
                        )
                conn.commit()
                return self.get_manifest(user_id, artifact_id, manifest_id)

            latest = conn.execute(
                "SELECT manifest_version FROM provenance_manifests "
                "WHERE user_id=? AND artifact_id=? ORDER BY manifest_version DESC LIMIT 1",
                (user_id, artifact_id),
            ).fetchone()
            version = (latest["manifest_version"] + 1) if latest else 1
            status = "signed" if signature else "unsigned"
            cursor = conn.execute(
                "INSERT INTO provenance_manifests("
                "user_id, artifact_id, manifest_version, schema_id, manifest_json, manifest_sha256, "
                "event_chain_head_sha256, status"
                ") VALUES (?, ?, ?, ?, ?, ?, ?, ?) RETURNING id",
                (
                    user_id, artifact_id, version, schema_id, manifest_json,
                    manifest_sha256, event_chain_head_sha256, status,
                ),
            )
            manifest_id = cursor.fetchone()["id"]
            if signature:
                conn.execute(
                    "INSERT INTO provenance_signatures("
                    "user_id, manifest_id, algorithm, key_id, signature_base64, public_key_base64, trust_level"
                    ") VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        user_id, manifest_id, signature["algorithm"], signature["key_id"],
                        signature["signature_base64"], signature["public_key_base64"],
                        signature["trust_level"],
                    ),
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        return self.get_manifest(user_id, artifact_id, manifest_id)

    @staticmethod
    def _connection():
        from database import get_connection
        return get_connection()
