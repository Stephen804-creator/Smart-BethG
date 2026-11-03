"""Portable Smart BethG provenance manifests and Ed25519 signing."""
import base64
import hmac
import json
import re

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

import config
from repositories.provenance_contracts import canonical_json, sha256_hex
from repositories.provenance_repository import ProvenanceRepository
from services.artifact_service import ArtifactService


MANIFEST_SCHEMA_ID = "urn:smartbethg:asset-provenance:manifest:v1"
MANIFEST_SCHEMA_VERSION = 1
MAX_MANIFEST_BYTES = 256 * 1024
_KEY_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_PUBLIC_TRUST_NOTE = (
    "This is a Smart BethG Ed25519 signature. A configured or development key "
    "does not establish public trust, legal identity, or C2PA certification."
)


class ProvenanceManifestService:
    def __init__(
        self, repository=None, artifact_service=None, private_key_bytes=None,
        key_id=None, trust_level=None,
    ):
        self.repository = repository or ProvenanceRepository()
        self.artifacts = artifact_service or ArtifactService()
        self._private_key_bytes = private_key_bytes
        self._key_id = key_id
        self._trust_level = trust_level

    def _signer(self):
        key_bytes = self._private_key_bytes
        if key_bytes is None:
            encoded = config.PROVENANCE_SIGNING_PRIVATE_KEY_B64
            if not encoded:
                return None
            try:
                key_bytes = base64.b64decode(encoded, validate=True)
            except (ValueError, TypeError) as exc:
                raise ValueError("Configured provenance signing key is not valid base64.") from exc
        if not isinstance(key_bytes, bytes) or len(key_bytes) != 32:
            raise ValueError("Ed25519 provenance private keys must contain exactly 32 raw bytes.")
        key_id = self._key_id if self._key_id is not None else config.PROVENANCE_SIGNING_KEY_ID
        if not isinstance(key_id, str) or not _KEY_ID_RE.fullmatch(key_id):
            raise ValueError("A valid provenance signing key ID is required.")
        trust_level = self._trust_level or config.PROVENANCE_SIGNING_TRUST_LEVEL
        if trust_level not in {"development", "configured"}:
            raise ValueError("Unsupported provenance signing trust level.")
        private_key = Ed25519PrivateKey.from_private_bytes(key_bytes)
        public_key = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        return private_key, public_key, key_id, trust_level

    def _snapshot(self, user_id, artifact_id):
        artifact = self.artifacts.get(user_id, artifact_id)
        if not artifact:
            raise LookupError("Artifact not found.")
        content, record = self.artifacts.read_bytes(user_id, artifact_id)
        if content is None or not record:
            raise ValueError("Asset bytes are unavailable and cannot be manifested.")
        actual_hash = sha256_hex(content)
        if not hmac.compare_digest(actual_hash, str(artifact.get("checksum_sha256") or "")):
            raise ValueError("Asset bytes do not match the stored SHA-256 identity.")
        integrity = self.repository.verify_chain(user_id, artifact_id)
        if not integrity["valid"]:
            raise ValueError("Provenance event chain is invalid; a manifest cannot be generated.")
        events = self.repository.list_events(user_id, artifact_id)
        return artifact, content, actual_hash, events, integrity

    @staticmethod
    def _event_payload(row):
        try:
            payload = json.loads(row["payload_json"])
            return payload if isinstance(payload, dict) else {}
        except (TypeError, ValueError):
            return {}

    @staticmethod
    def _portable_event_payload(event_type, payload):
        allowed = {
            "summary", "source_sha256", "fallback_used", "output_sha256",
            "instruction_text_included", "instruction_text", "role",
            "content_type", "size_bytes", "checksum_sha256", "source_filename",
            "attribution_basis",
        }
        safe = {key: value for key, value in payload.items() if key in allowed}
        if event_type == "human_edit" and not payload.get("instruction_text_included"):
            safe.pop("instruction_text", None)
        return safe

    def _build_manifest(self, artifact, asset_hash, events, integrity, signing):
        contributors = []
        contributor_keys = set()
        sources = []
        history = []
        origin = "recorded_in_smart_bethg"

        for row in events:
            event_type = row["event_type"]
            actor_type = row["actor_type"]
            payload = self._event_payload(row)
            provider = row.get("provider")
            model = row.get("model")
            agent_id = row.get("agent_id")

            if event_type == "asset_uploaded":
                origin = "user_uploaded"
            elif event_type == "ai_contribution":
                contributor = {
                    "role": "ai_provider",
                    "provider": provider or "unknown",
                    "model": model or "unknown",
                }
                key = ("ai_provider", provider, model)
                if key not in contributor_keys:
                    contributors.append(contributor)
                    contributor_keys.add(key)
            elif event_type == "agent_contribution":
                contributor = {
                    "role": "orchestrator",
                    "name": "Smart BethG",
                    "agent_id": agent_id or "unknown",
                }
                key = ("orchestrator", agent_id)
                if key not in contributor_keys:
                    contributors.append(contributor)
                    contributor_keys.add(key)
            elif actor_type == "human":
                key = ("human", row.get("actor_label"))
                if key not in contributor_keys:
                    contributors.append({"role": "human_contributor", "name": "Human contributor"})
                    contributor_keys.add(key)

            if event_type == "source_attached":
                source_hash = payload.get("source_sha256")
                if isinstance(source_hash, str) and re.fullmatch(r"[0-9a-f]{64}", source_hash):
                    sources.append({
                        "ref": f"urn:smartbethg:asset:sha256:{source_hash}",
                        "sha256": source_hash,
                        "relationship": "source",
                    })

            actor_label = (
                "Human contributor" if actor_type == "human"
                else row.get("actor_label") or actor_type
            )
            item = {
                "sequence": row["sequence_number"],
                "event_type": event_type,
                "actor": {"type": actor_type, "label": actor_label},
                "timestamp": row["created_at"],
            }
            if provider:
                item["provider"] = provider
            if model:
                item["model"] = model
            if agent_id:
                item["agent_id"] = agent_id
            portable_payload = self._portable_event_payload(event_type, payload)
            if portable_payload:
                item["details"] = portable_payload
            history.append(item)

        return {
            "schema_id": MANIFEST_SCHEMA_ID,
            "schema_version": MANIFEST_SCHEMA_VERSION,
            "asset": {
                "ref": f"urn:smartbethg:asset:sha256:{asset_hash}",
                "name": artifact["name"],
                "media_type": artifact.get("content_type") or "application/octet-stream",
                "artifact_type": artifact.get("artifact_type") or "unknown",
                "size_bytes": artifact.get("size_bytes", 0),
                "sha256": asset_hash,
            },
            "created_at": artifact.get("created_at"),
            "origin": origin,
            "contributors": contributors,
            "sources": sources,
            "history": history,
            "event_chain": {
                "events_count": integrity["events_checked"],
                "head_sha256": integrity["head_sha256"],
            },
            "signing": signing,
            "standards": {
                "format": "smartbethg-internal-provenance-json",
                "c2pa_compatible": False,
                "c2pa_certified": False,
            },
        }

    def _create_or_reuse(self, user_id, artifact_id, signing, signer=None):
        artifact, content, asset_hash, events, integrity = self._snapshot(user_id, artifact_id)
        latest = self.repository.get_latest_manifest(user_id, artifact_id)
        if latest:
            try:
                latest_json = json.loads(latest["manifest_json"])
            except (TypeError, ValueError):
                latest_json = {}
            same_snapshot = (
                latest.get("event_chain_head_sha256") == integrity["head_sha256"]
                and latest_json.get("asset", {}).get("sha256") == asset_hash
                and latest_json.get("signing") == signing
            )
            if same_snapshot:
                return latest

        manifest = self._build_manifest(artifact, asset_hash, events, integrity, signing)
        manifest_json = canonical_json(manifest)
        if len(manifest_json.encode("utf-8")) > MAX_MANIFEST_BYTES:
            raise ValueError("Provenance manifest exceeds the 256 KiB limit.")
        manifest_digest = sha256_hex(manifest_json)

        signature = None
        if signer:
            private_key, public_key, key_id, trust_level = signer
            signature = {
                "algorithm": "Ed25519",
                "key_id": key_id,
                "signature_base64": base64.b64encode(
                    private_key.sign(manifest_digest.encode("ascii"))
                ).decode("ascii"),
                "public_key_base64": base64.b64encode(public_key).decode("ascii"),
                "trust_level": trust_level,
            }
        return self.repository.save_manifest(
            user_id, artifact_id, MANIFEST_SCHEMA_ID, manifest_json,
            manifest_digest, integrity["head_sha256"], signature=signature,
        )

    @staticmethod
    def _public_record(record):
        if not record:
            return None
        try:
            manifest = json.loads(record["manifest_json"])
        except (TypeError, ValueError):
            manifest = None
        return {
            "id": record["id"],
            "artifact_id": record["artifact_id"],
            "manifest_version": record["manifest_version"],
            "schema_id": record["schema_id"],
            "manifest_sha256": record["manifest_sha256"],
            "event_chain_head_sha256": record["event_chain_head_sha256"],
            "status": record["status"],
            "created_at": record["created_at"],
            "manifest": manifest,
        }

    def generate_manifest(self, user_id, artifact_id):
        artifact, content, asset_hash, events, integrity = self._snapshot(user_id, artifact_id)
        latest = self.repository.get_latest_manifest(user_id, artifact_id)
        if latest:
            try:
                latest_json = json.loads(latest["manifest_json"])
            except (TypeError, ValueError):
                latest_json = {}
            if (
                latest.get("event_chain_head_sha256") == integrity["head_sha256"]
                and latest_json.get("asset", {}).get("sha256") == asset_hash
            ):
                return self._public_record(latest)
        signing = {
            "status": "unsigned",
            "algorithm": None,
            "key_id": None,
            "trust_level": "none",
            "trust_note": "No signature is present. Verification will not report this manifest as trusted.",
        }
        record = self._create_or_reuse(user_id, artifact_id, signing)
        return self._public_record(record)

    def sign_manifest(self, user_id, artifact_id):
        signer = self._signer()
        if signer is None:
            return self.generate_manifest(user_id, artifact_id)
        _, _, key_id, trust_level = signer
        signing = {
            "status": "signed",
            "algorithm": "Ed25519",
            "key_id": key_id,
            "trust_level": trust_level,
            "trust_note": _PUBLIC_TRUST_NOTE,
        }
        record = self._create_or_reuse(user_id, artifact_id, signing, signer=signer)
        return self._public_record(record)

    def get_latest_manifest(self, user_id, artifact_id):
        if not self.artifacts.get(user_id, artifact_id):
            raise LookupError("Artifact not found.")
        return self._public_record(self.repository.get_latest_manifest(user_id, artifact_id))

    def verify_manifest(self, user_id, artifact_id, manifest_id=None):
        artifact = self.artifacts.get(user_id, artifact_id)
        if not artifact:
            raise LookupError("Artifact not found.")
        record = (
            self.repository.get_manifest(user_id, artifact_id, manifest_id)
            if manifest_id is not None
            else self.repository.get_latest_manifest(user_id, artifact_id)
        )
        if not record:
            return {"valid": False, "status": "missing", "reason": "manifest_not_found"}

        try:
            manifest = json.loads(record["manifest_json"])
            if not isinstance(manifest, dict) or not isinstance(manifest.get("asset"), dict):
                raise ValueError("Manifest structure is invalid.")
            recalculated = sha256_hex(canonical_json(manifest))
        except (TypeError, ValueError):
            return {"valid": False, "status": "invalid", "reason": "manifest_malformed"}
        if not hmac.compare_digest(recalculated, str(record["manifest_sha256"])):
            return {"valid": False, "status": "invalid", "reason": "manifest_digest_mismatch"}

        try:
            content, stored = self.artifacts.read_bytes(user_id, artifact_id)
        except ValueError:
            content, stored = None, None
        if content is None or not stored:
            return {"valid": False, "status": "invalid", "reason": "asset_unavailable_or_changed"}
        asset_hash = sha256_hex(content)
        if (
            not hmac.compare_digest(asset_hash, str(manifest.get("asset", {}).get("sha256", "")))
            or len(content) != manifest.get("asset", {}).get("size_bytes")
        ):
            return {"valid": False, "status": "invalid", "reason": "asset_digest_mismatch"}

        chain = self.repository.verify_chain(
            user_id, artifact_id, expected_head=record["event_chain_head_sha256"]
        )
        if not chain["valid"]:
            return {"valid": False, "status": "invalid", "reason": "event_chain_" + chain["reason"]}

        signatures = self.repository.list_signatures(user_id, record["id"])
        if not signatures:
            return {
                "valid": False, "status": "unsigned", "reason": "signature_missing",
                "manifest_id": record["id"], "manifest_sha256": record["manifest_sha256"],
            }

        signing = manifest.get("signing") or {}
        for signature_record in signatures:
            if (
                signature_record["algorithm"] != "Ed25519"
                or signature_record["key_id"] != signing.get("key_id")
                or signature_record["trust_level"] != signing.get("trust_level")
            ):
                continue
            try:
                public_bytes = base64.b64decode(signature_record["public_key_base64"], validate=True)
                signature_bytes = base64.b64decode(signature_record["signature_base64"], validate=True)
                public_key = Ed25519PublicKey.from_public_bytes(public_bytes)
                public_key.verify(signature_bytes, record["manifest_sha256"].encode("ascii"))
            except Exception:
                continue
            return {
                "valid": True,
                "status": "valid_signature",
                "reason": None,
                "manifest_id": record["id"],
                "manifest_sha256": record["manifest_sha256"],
                "event_chain_head_sha256": record["event_chain_head_sha256"],
                "trust_level": signature_record["trust_level"],
                "trust_note": _PUBLIC_TRUST_NOTE,
            }
        return {
            "valid": False, "status": "invalid", "reason": "signature_invalid",
            "manifest_id": record["id"], "manifest_sha256": record["manifest_sha256"],
        }
