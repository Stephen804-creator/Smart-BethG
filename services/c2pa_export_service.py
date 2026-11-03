"""C2PA embedding, signing, and verification for SDK-supported media."""
import io
import json
import os
import tempfile

import config
from repositories.provenance_repository import ProvenanceRepository
from repositories.provenance_contracts import sha256_hex
from services.artifact_service import ArtifactService
from services.provenance_manifest_service import ProvenanceManifestService


TRAINED_ALGORITHMIC_MEDIA = (
    "http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia"
)
SOFTWARE_AGENT = {"name": "Smart BethG", "version": "1.0"}
SUPPORTED_ALGORITHMS = {"PS256", "ES256", "ES384", "ES512", "ED25519"}


class C2paExportService:
    def __init__(
        self, artifact_service=None, provenance_repository=None,
        manifest_service=None, signer_cert_pem=None, signer_private_key_pem=None,
        signing_algorithm=None, timestamp_url=None, trust_anchors_pem=None,
    ):
        self.artifacts = artifact_service or ArtifactService()
        self.repository = provenance_repository or ProvenanceRepository()
        self.manifests = manifest_service or ProvenanceManifestService(
            self.repository, self.artifacts
        )
        self.signer_cert_pem = (
            config.C2PA_SIGN_CERT_PEM if signer_cert_pem is None else signer_cert_pem
        )
        self.signer_private_key_pem = (
            config.C2PA_SIGN_PRIVATE_KEY_PEM
            if signer_private_key_pem is None else signer_private_key_pem
        )
        self.signing_algorithm = (
            config.C2PA_SIGN_ALGORITHM if signing_algorithm is None else signing_algorithm
        ).upper()
        self.timestamp_url = config.C2PA_TSA_URL if timestamp_url is None else timestamp_url
        self.trust_anchors_pem = (
            config.C2PA_TRUST_ANCHORS_PEM if trust_anchors_pem is None else trust_anchors_pem
        )

    @staticmethod
    def _sdk():
        try:
            import c2pa
        except ImportError as exc:
            raise RuntimeError(
                "The optional C2PA SDK is not installed. Install requirements-c2pa.txt."
            ) from exc
        return c2pa

    def _context(self, c2pa):
        if self.trust_anchors_pem:
            settings = c2pa.Settings.from_dict({
                "verify": {
                    "verify_after_reading": True,
                    "verify_after_sign": True,
                    "verify_cert_anchors": True,
                    "remote_manifest_fetch": False,
                    "ocsp_fetch": False,
                },
                "trust": {"user_anchors": self.trust_anchors_pem},
            })
            return c2pa.Context(settings)
        # Keep the SDK's default C2PA trust policy. A missing custom anchor
        # must never silently disable certificate-chain verification.
        return c2pa.Context()

    @staticmethod
    def _validation_state(reader):
        state = reader.get_validation_state()
        value = getattr(state, "name", str(state)).split(".")[-1].lower()
        return value, value in {"valid", "trusted"}, value == "trusted"

    @staticmethod
    def _validation_results(reader):
        try:
            results = reader.get_validation_results()
            if isinstance(results, str):
                return json.loads(results)
            return results
        except Exception:
            return None

    @staticmethod
    def _event_payload(row):
        try:
            value = json.loads(row["payload_json"])
            return value if isinstance(value, dict) else {}
        except (TypeError, ValueError):
            return {}

    def capabilities(self):
        try:
            c2pa = self._sdk()
            supported = sorted(set(c2pa.Builder.get_supported_mime_types()))
            available = True
            error = None
        except Exception as exc:
            supported = []
            available = False
            error = str(exc)
        return {
            "sdk_available": available,
            "signing_credentials_configured": bool(
                self.signer_cert_pem and self.signer_private_key_pem
            ),
            "timestamp_authority_configured": bool(self.timestamp_url),
            "trust_anchors_configured": bool(self.trust_anchors_pem),
            "supported_mime_types": supported,
            "signing_algorithm": self.signing_algorithm,
            "error": error,
            "trust_note": (
                "A configured certificate is not automatically trusted by independent "
                "C2PA validators or included in the official C2PA Trust List."
            ),
        }

    def export(self, user_id, artifact_id):
        c2pa = self._sdk()
        artifact = self.artifacts.get(user_id, artifact_id)
        if not artifact:
            raise LookupError("Artifact not found.")
        content, record = self.artifacts.read_bytes(user_id, artifact_id)
        if content is None or not record:
            raise ValueError("Asset bytes are unavailable for C2PA signing.")
        media_type = (record.get("content_type") or "").split(";", 1)[0].strip().lower()
        supported = set(c2pa.Builder.get_supported_mime_types())
        if media_type not in supported:
            raise ValueError(
                f"C2PA signing is not supported for {media_type or 'unknown media type'} "
                "by the installed SDK. The internal JSON provenance manifest remains available."
            )

        internal_manifest = self.manifests.generate_manifest(user_id, artifact_id)
        internal_manifest_hash = internal_manifest["manifest_sha256"]
        event_rows = self.repository.list_events(user_id, artifact_id)
        has_ai_contribution = any(
            row["event_type"] == "ai_contribution" for row in event_rows
        )
        source_rows = [
            row for row in event_rows if row["event_type"] == "source_attached"
        ]
        omitted_sources = []
        source_ingredients = []
        source_references = []
        for index, row in enumerate(source_rows, start=1):
            payload = self._event_payload(row)
            source_id = payload.get("source_artifact_id")
            source_hash = payload.get("source_sha256")
            if not isinstance(source_id, int) or isinstance(source_id, bool):
                raise ValueError("A source attachment is missing its owner-scoped artifact reference.")
            source = self.artifacts.get(user_id, source_id)
            if not source:
                raise ValueError("A recorded source asset is no longer available to this owner.")
            source_bytes, source_record = self.artifacts.read_bytes(user_id, source_id)
            if source_bytes is None or not source_record:
                raise ValueError("A recorded source asset could not be read.")
            actual_source_hash = sha256_hex(source_bytes)
            if actual_source_hash != source_hash:
                raise ValueError("A recorded source asset no longer matches its provenance hash.")
            source_mime = (source_record.get("content_type") or "").split(";", 1)[0].lower()
            source_references.append({
                "source_id": source_id,
                "source_sha256": actual_source_hash,
                "relationship": "componentOf",
            })
            if source_mime not in supported:
                omitted_sources.append({
                    "source_sha256": actual_source_hash,
                    "reason": "source_media_type_not_supported_by_c2pa_sdk",
                })
                continue
            label = f"smartbethg-source-{index}-{actual_source_hash[:12]}"
            source_ingredients.append({
                "label": label,
                "name": source["name"],
                "mime_type": source_mime,
                "content": source_bytes,
                "sha256": actual_source_hash,
                "source_id": source_id,
            })

        manifest_definition = {
            "claim_generator_info": [{"name": "Smart BethG", "version": "1.0"}],
            "title": artifact["name"],
            "format": media_type,
            "assertions": [{
                "label": "io.github.stephen804creator.smartbethg.provenance",
                "data": {
                    "internal_manifest_sha256": internal_manifest_hash,
                    "event_chain_head_sha256": internal_manifest["event_chain_head_sha256"],
                    "source_reference_count": len(source_references),
                },
            }],
        }
        signer_info = self._signer_info(c2pa)
        context = self._context(c2pa)
        signed_stream = io.BytesIO()
        try:
            with context:
                with c2pa.Signer.from_info(signer_info) as active_signer:
                    with c2pa.Builder(manifest_definition, context) as builder:
                        if has_ai_contribution:
                            builder.set_intent(
                                c2pa.C2paBuilderIntent.CREATE,
                                c2pa.C2paDigitalSourceType.TRAINED_ALGORITHMIC_MEDIA,
                            )
                        else:
                            original_label = "smartbethg-original-input"
                            builder.add_ingredient(
                                {
                                    "title": artifact["name"],
                                    "relationship": "parentOf",
                                    "label": original_label,
                                },
                                media_type,
                                io.BytesIO(content),
                            )
                            builder.set_intent(c2pa.C2paBuilderIntent.EDIT)

                        for ingredient in source_ingredients:
                            builder.add_ingredient(
                                {
                                    "title": ingredient["name"],
                                    "relationship": "componentOf",
                                    "label": ingredient["label"],
                                },
                                ingredient["mime_type"],
                                io.BytesIO(ingredient["content"]),
                            )
                            builder.add_action({
                                "action": "c2pa.placed",
                                "softwareAgent": SOFTWARE_AGENT,
                                "parameters": {
                                    "ingredientIds": [ingredient["label"]],
                                },
                                "description": "Source asset attached to this Smart BethG artifact.",
                            })

                        for row in event_rows:
                            if row["event_type"] == "human_edit":
                                details = self._event_payload(row)
                                summary = details.get("summary")
                                builder.add_action({
                                    "action": "c2pa.edited",
                                    "softwareAgent": SOFTWARE_AGENT,
                                    "description": summary or "A human edit was recorded in Smart BethG.",
                                })

                        builder.sign(
                            active_signer, media_type,
                            io.BytesIO(content), signed_stream,
                        )

                signed_stream.seek(0)
                with c2pa.Reader(media_type, signed_stream, context=context) as reader:
                    store = json.loads(reader.json())
                    active_label = store.get("active_manifest")
                    active_manifest = (store.get("manifests") or {}).get(active_label)
                    if not active_manifest or not active_manifest.get("signature_info"):
                        raise ValueError("The C2PA SDK did not produce a signed active manifest.")
                    validation_state, signature_verified, trusted = self._validation_state(reader)
                    validation_results = self._validation_results(reader)
        except ValueError:
            raise
        except Exception as exc:
            raise RuntimeError(f"C2PA signing or validation failed: {exc}") from exc

        signed_bytes = signed_stream.getvalue()
        if len(signed_bytes) > config.MAX_ASSET_UPLOAD_BYTES:
            raise ValueError("The signed C2PA asset exceeds the configured artifact size limit.")

        extension = os.path.splitext(artifact["name"])[1]
        stem = os.path.splitext(artifact["name"])[0]
        output_name = f"{stem}.c2pa{extension}" if extension else f"{artifact['name']}.c2pa"
        temporary_path = None
        try:
            with tempfile.NamedTemporaryFile(prefix="smartbethg-c2pa-", suffix=extension, delete=False) as handle:
                temporary_path = handle.name
                handle.write(signed_bytes)
                handle.flush()
                os.fsync(handle.fileno())
            output_artifact = self.artifacts.create_binary_from_path(
                user_id, output_name, temporary_path, media_type,
                provenance_event_type="transformation",
                provenance_actor_type="smart_bethg",
                provenance_actor_id="smart_bethg",
                provenance_actor_label="Smart BethG C2PA exporter",
                provenance_agent_id="c2pa_exporter",
                provenance_payload={
                    "operation": "c2pa_manifest_embedding",
                    "source_artifact_id": artifact_id,
                    "source_sha256": artifact["checksum_sha256"],
                    "internal_manifest_sha256": internal_manifest_hash,
                    "c2pa_signing_algorithm": self.signing_algorithm,
                    "c2pa_validation_state": validation_state,
                    "c2pa_signature_verified": signature_verified,
                    "c2pa_trusted": trusted,
                },
            )
        finally:
            if temporary_path:
                try:
                    os.unlink(temporary_path)
                except OSError:
                    pass

        output_source_references = [{
            "source_id": artifact_id,
            "source_sha256": artifact["checksum_sha256"],
            "relationship": "parentOf",
        }] if not has_ai_contribution else []
        output_source_references.extend(source_references)
        for source in output_source_references:
            self.repository.append_event(
                user_id, output_artifact["id"], "source_attached", "smart_bethg",
                actor_id="smart_bethg", actor_label="Smart BethG C2PA exporter",
                payload={
                    "source_artifact_id": source["source_id"],
                    "source_sha256": source["source_sha256"],
                    "relationship": source["relationship"],
                    "attribution_basis": "system_derived",
                },
            )
        output_internal_manifest = self.manifests.generate_manifest(
            user_id, output_artifact["id"]
        )
        output_artifact.pop("path", None)
        return {
            "artifact": output_artifact,
            "c2pa": {
                "status": "signed",
                "mime_type": media_type,
                "signing_algorithm": self.signing_algorithm,
                "validation_state": validation_state,
                "signature_verified": signature_verified,
                "trusted": trusted,
                "timestamp_authority_used": bool(self.timestamp_url),
                "internal_manifest_sha256": internal_manifest_hash,
                "active_manifest": active_label,
                "unembedded_sources": omitted_sources,
                "validation_results": validation_results,
                "trust_note": (
                    "A valid signature is not necessarily a trusted identity. "
                    "Independent trust depends on certificate chain, EKU, revocation, "
                    "timestamp, and verifier trust-list policy."
                ),
            },
            "internal_manifest": output_internal_manifest,
        }

    def _signer_info(self, c2pa):
        algorithm = getattr(c2pa.C2paSigningAlg, self.signing_algorithm, None)
        if algorithm is None:
            raise ValueError("The installed C2PA SDK does not support the configured signing algorithm.")
        if not self.signer_cert_pem or not self.signer_private_key_pem:
            raise RuntimeError("C2PA signing credentials are not configured.")
        return c2pa.C2paSignerInfo(
            alg=algorithm,
            sign_cert=self.signer_cert_pem.encode("utf-8"),
            private_key=self.signer_private_key_pem.encode("utf-8"),
            ta_url=self.timestamp_url.encode("utf-8") if self.timestamp_url else None,
        )

    def verify_artifact(self, user_id, artifact_id):
        c2pa = self._sdk()
        artifact = self.artifacts.get(user_id, artifact_id)
        if not artifact:
            raise LookupError("Artifact not found.")
        content, record = self.artifacts.read_bytes(user_id, artifact_id)
        if content is None or not record:
            raise ValueError("Asset bytes are unavailable.")
        media_type = (record.get("content_type") or "").split(";", 1)[0].lower()
        supported = set(c2pa.Builder.get_supported_mime_types())
        if media_type not in supported:
            raise ValueError(f"C2PA validation is not supported for {media_type or 'unknown media type'}.")
        context = self._context(c2pa)
        try:
            with context:
                with c2pa.Reader(media_type, io.BytesIO(content), context=context) as reader:
                    store = json.loads(reader.json())
                    active_label = store.get("active_manifest")
                    active_manifest = (store.get("manifests") or {}).get(active_label)
                    if not active_manifest:
                        return {
                            "has_c2pa_manifest": False,
                            "valid": False,
                            "trusted": False,
                            "status": "no_manifest",
                        }
                    state, signature_verified, trusted = self._validation_state(reader)
                    return {
                        "has_c2pa_manifest": True,
                        "valid": signature_verified,
                        "trusted": trusted,
                        "status": state,
                        "active_manifest": active_label,
                        "title": active_manifest.get("title"),
                        "claim_generator": active_manifest.get("claim_generator"),
                        "signature_info": active_manifest.get("signature_info"),
                        "validation_results": self._validation_results(reader),
                        "trust_note": (
                            "Trusted is reported only when the configured verifier trust policy "
                            "accepts the certificate chain. Valid without Trusted means the "
                            "signature verifies but the signer is not established as trusted."
                        ),
                    }
        except Exception as exc:
            return {
                "has_c2pa_manifest": False,
                "valid": False,
                "trusted": False,
                "status": "invalid_or_unreadable",
                "reason": str(exc),
            }
