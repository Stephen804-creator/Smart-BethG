"""Manifest determinism, Ed25519 signing, and verification tests."""
import base64
import json
import os

from database import get_connection
from repositories.provenance_repository import ProvenanceRepository
from services.artifact_service import ArtifactService
from services.auth_service import create_user
from services.provenance_manifest_service import ProvenanceManifestService
from tests.base import SmartBethGTestCase


class TestProvenanceManifestService(SmartBethGTestCase):
    def setUp(self):
        super().setUp()
        self.owner = create_user("manifest-owner", "password123")
        self.other = create_user("manifest-other", "password123")
        self.artifacts = ArtifactService()
        self.artifact = self.artifacts.create(
            self.owner["id"], "manifest-source.txt", "Portable manifest source content."
        )
        self.repository = ProvenanceRepository()
        self.private_key = bytes(range(32))
        self.service = ProvenanceManifestService(
            self.repository, self.artifacts,
            private_key_bytes=self.private_key,
            key_id="test-ed25519-key",
            trust_level="development",
        )

    def test_manifest_is_deterministic_and_contains_no_private_storage_details(self):
        first = self.service.generate_manifest(self.owner["id"], self.artifact["id"])
        second = self.service.generate_manifest(self.owner["id"], self.artifact["id"])
        self.assertEqual(first["id"], second["id"])
        self.assertEqual(first["manifest_sha256"], second["manifest_sha256"])
        self.assertEqual(first["manifest_version"], 1)
        manifest = first["manifest"]
        self.assertEqual(manifest["asset"]["sha256"], self.artifact["checksum_sha256"])
        self.assertEqual(manifest["standards"]["c2pa_certified"], False)
        self.assertNotIn("path", json.dumps(manifest))
        self.assertNotIn("user_id", json.dumps(manifest))
        self.assertNotIn(os.path.abspath("."), json.dumps(manifest))

    def test_unsigned_manifest_never_verifies_as_valid(self):
        unsigned_service = ProvenanceManifestService(self.repository, self.artifacts)
        manifest = unsigned_service.sign_manifest(self.owner["id"], self.artifact["id"])
        self.assertEqual(manifest["status"], "unsigned")
        result = unsigned_service.verify_manifest(self.owner["id"], self.artifact["id"])
        self.assertFalse(result["valid"])
        self.assertEqual(result["status"], "unsigned")
        self.assertEqual(result["reason"], "signature_missing")

    def test_ed25519_signature_round_trip_and_historical_chain_prefix(self):
        signed = self.service.sign_manifest(self.owner["id"], self.artifact["id"])
        self.assertEqual(signed["status"], "signed")
        self.assertEqual(signed["manifest"]["signing"]["key_id"], "test-ed25519-key")
        valid = self.service.verify_manifest(self.owner["id"], self.artifact["id"])
        self.assertTrue(valid["valid"])
        self.assertEqual(valid["status"], "valid_signature")
        self.assertEqual(valid["trust_level"], "development")

        self.repository.append_event(
            self.owner["id"], self.artifact["id"], "review", "human",
            actor_id=str(self.owner["id"]), payload={"summary": "Reviewed after signing."},
        )
        old_manifest = self.service.verify_manifest(
            self.owner["id"], self.artifact["id"], manifest_id=signed["id"]
        )
        self.assertTrue(old_manifest["valid"])
        newer = self.service.generate_manifest(self.owner["id"], self.artifact["id"])
        self.assertEqual(newer["manifest_version"], 2)
        self.assertEqual(newer["status"], "unsigned")

    def test_changed_asset_bytes_fail_verification(self):
        signed = self.service.sign_manifest(self.owner["id"], self.artifact["id"])
        object_name = os.path.basename(self.artifact["path"])
        self.artifacts.storage.put_bytes(
            "artifacts", self.owner["id"], object_name, b"changed bytes"
        )
        result = self.service.verify_manifest(
            self.owner["id"], self.artifact["id"], manifest_id=signed["id"]
        )
        self.assertFalse(result["valid"])
        self.assertEqual(result["reason"], "asset_unavailable_or_changed")

    def test_changed_manifest_json_fails_digest_verification(self):
        signed = self.service.sign_manifest(self.owner["id"], self.artifact["id"])
        conn = get_connection()
        try:
            conn.execute(
                "UPDATE provenance_manifests SET manifest_json=? WHERE id=? AND user_id=?",
                ('{"tampered":true}', signed["id"], self.owner["id"]),
            )
            conn.commit()
        finally:
            conn.close()
        result = self.service.verify_manifest(
            self.owner["id"], self.artifact["id"], manifest_id=signed["id"]
        )
        self.assertFalse(result["valid"])
        self.assertEqual(result["reason"], "manifest_digest_mismatch")

    def test_changed_public_key_fails_signature_verification(self):
        signed = self.service.sign_manifest(self.owner["id"], self.artifact["id"])
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        other_public = Ed25519PrivateKey.from_private_bytes(bytes(reversed(range(32)))).public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        conn = get_connection()
        try:
            conn.execute(
                "UPDATE provenance_signatures SET public_key_base64=? WHERE manifest_id=? AND user_id=?",
                (
                    base64.b64encode(other_public).decode("ascii"),
                    signed["id"], self.owner["id"],
                ),
            )
            conn.commit()
        finally:
            conn.close()
        result = self.service.verify_manifest(
            self.owner["id"], self.artifact["id"], manifest_id=signed["id"]
        )
        self.assertFalse(result["valid"])
        self.assertEqual(result["reason"], "signature_invalid")

    def test_manifest_lookup_is_owner_scoped(self):
        signed = self.service.sign_manifest(self.owner["id"], self.artifact["id"])
        with self.assertRaises(LookupError):
            self.service.get_latest_manifest(self.other["id"], self.artifact["id"])
        with self.assertRaises(LookupError):
            self.service.verify_manifest(
                self.other["id"], self.artifact["id"], manifest_id=signed["id"]
            )


if __name__ == "__main__":
    import unittest
    unittest.main()
