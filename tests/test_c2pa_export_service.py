"""End-to-end C2PA media signing and verification tests."""
import base64
import importlib.util
import io
import json
import os
import struct
import tempfile
import unittest
import zlib
from datetime import datetime, timedelta, timezone

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID, ObjectIdentifier

from repositories.provenance_repository import ProvenanceRepository
from services.artifact_service import ArtifactService
from services.auth_service import create_user
from services.c2pa_export_service import C2paExportService
from services.provenance_manifest_service import ProvenanceManifestService
from tests.base import SmartBethGTestCase

HAS_C2PA = importlib.util.find_spec("c2pa") is not None


def _png_chunk(kind, payload):
    return (
        struct.pack(">I", len(payload)) + kind + payload
        + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)
    )


def _valid_png():
    header = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    pixels = zlib.compress(b"\x00\x20\x80\xe0")
    return (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", header)
        + _png_chunk(b"IDAT", pixels)
        + _png_chunk(b"IEND", b"")
    )


def _development_signing_chain():
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    root_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    root_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Smart BethG Test Root")])
    root = (
        x509.CertificateBuilder()
        .subject_name(root_name)
        .issuer_name(root_name)
        .public_key(root_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=30))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True, content_commitment=False,
                key_encipherment=False, data_encipherment=False,
                key_agreement=False, key_cert_sign=True, crl_sign=True,
                encipher_only=None, decipher_only=None,
            ),
            critical=True,
        )
        .sign(root_key, hashes.SHA256())
    )

    leaf_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    leaf_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Smart BethG Development Signer")])
    leaf = (
        x509.CertificateBuilder()
        .subject_name(leaf_name)
        .issuer_name(root_name)
        .public_key(leaf_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=30))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True, content_commitment=True,
                key_encipherment=True, data_encipherment=False,
                key_agreement=False, key_cert_sign=False, crl_sign=False,
                encipher_only=None, decipher_only=None,
            ),
            critical=True,
        )
        .add_extension(
            x509.ExtendedKeyUsage([
                ObjectIdentifier("1.3.6.1.4.1.62558.2.1"),
                ExtendedKeyUsageOID.DOCUMENT_SIGNING,
            ]),
            critical=False,
        )
        .add_extension(
            x509.AuthorityKeyIdentifier.from_issuer_public_key(root_key.public_key()),
            critical=False,
        )
        .sign(root_key, hashes.SHA256())
    )
    leaf_pem = leaf.public_bytes(serialization.Encoding.PEM).decode("ascii")
    root_pem = root.public_bytes(serialization.Encoding.PEM).decode("ascii")
    private_pem = leaf_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode("ascii")
    return leaf_pem + root_pem, private_pem, root_pem


@unittest.skipUnless(HAS_C2PA, "Optional C2PA SDK is not installed.")
class TestC2paExportService(SmartBethGTestCase):
    def setUp(self):
        super().setUp()
        self.owner = create_user("c2pa-owner", "password123")
        self.artifacts = ArtifactService()
        self.repository = ProvenanceRepository()
        self.manifests = ProvenanceManifestService(self.repository, self.artifacts)
        cert_pem, key_pem, root_pem = _development_signing_chain()
        self.service = C2paExportService(
            artifact_service=self.artifacts,
            provenance_repository=self.repository,
            manifest_service=self.manifests,
            signer_cert_pem=cert_pem,
            signer_private_key_pem=key_pem,
            signing_algorithm="PS256",
            trust_anchors_pem=root_pem,
        )

    def _create_png_artifact(self, ai_generated=False):
        png = _valid_png()
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as handle:
            path = handle.name
            handle.write(png)
        try:
            if ai_generated:
                artifact = self.artifacts.create_binary_from_path(
                    self.owner["id"], "ai-generated.png", path, "image/png",
                    provenance_event_type="ai_contribution",
                    provenance_actor_type="provider",
                    provenance_actor_id="openai",
                    provenance_actor_label="OpenAI",
                    provenance_agent_id="image_generator",
                    provenance_provider="openai",
                    provenance_model="gpt-image-test",
                )
            else:
                artifact = self.artifacts.create_binary_from_path(
                    self.owner["id"], "uploaded.png", path, "image/png"
                )
            return artifact, png
        finally:
            os.unlink(path)

    def test_capabilities_and_plain_asset_verification(self):
        capabilities = self.service.capabilities()
        self.assertTrue(capabilities["sdk_available"])
        self.assertIn("image/png", capabilities["supported_mime_types"])
        artifact, _ = self._create_png_artifact()
        result = self.service.verify_artifact(self.owner["id"], artifact["id"])
        self.assertFalse(result["has_c2pa_manifest"])
        self.assertEqual(result["status"], "no_manifest")

    def test_user_uploaded_asset_is_signed_with_parent_ingredient_and_verified(self):
        artifact, _ = self._create_png_artifact()
        result = self.service.export(self.owner["id"], artifact["id"])
        output = result["artifact"]
        self.assertNotEqual(output["id"], artifact["id"])
        self.assertEqual(result["c2pa"]["status"], "signed")
        self.assertTrue(result["c2pa"]["signature_verified"])
        self.assertTrue(result["c2pa"]["trusted"])

        verified = self.service.verify_artifact(self.owner["id"], output["id"])
        self.assertTrue(verified["has_c2pa_manifest"])
        self.assertTrue(verified["valid"])
        self.assertTrue(verified["trusted"])

        events = self.repository.list_events(self.owner["id"], output["id"])
        self.assertEqual([row["event_type"] for row in events], [
            "transformation", "agent_contribution", "source_attached"
        ])
        source_payload = json.loads(events[2]["payload_json"])
        self.assertEqual(source_payload["source_artifact_id"], artifact["id"])
        self.assertEqual(source_payload["source_sha256"], artifact["checksum_sha256"])

    def test_ai_generated_asset_uses_trained_algorithmic_media_intent(self):
        artifact, _ = self._create_png_artifact(ai_generated=True)
        result = self.service.export(self.owner["id"], artifact["id"])
        self.assertTrue(result["c2pa"]["signature_verified"])
        output = result["artifact"]
        import c2pa
        content, record = self.artifacts.read_bytes(self.owner["id"], output["id"])
        with self.service._context(c2pa) as context:
            with c2pa.Reader("image/png", io.BytesIO(content), context=context) as reader:
                active = reader.get_active_manifest()
        manifest_text = json.dumps(active)
        self.assertIn("trainedAlgorithmicMedia", manifest_text)
        ai_history = next(
            item for item in result["internal_manifest"]["manifest"]["history"]
            if item["event_type"] == "ai_contribution"
        )
        self.assertEqual(ai_history["model"], "gpt-image-test")

    def test_missing_c2pa_credentials_never_claims_to_sign(self):
        artifact, _ = self._create_png_artifact()
        unconfigured = C2paExportService(
            artifact_service=self.artifacts,
            provenance_repository=self.repository,
            manifest_service=self.manifests,
            signer_cert_pem="",
            signer_private_key_pem="",
        )
        with self.assertRaisesRegex(RuntimeError, "credentials are not configured"):
            unconfigured.export(self.owner["id"], artifact["id"])

    def test_unsupported_text_asset_is_not_mislabeled_as_c2pa_signed(self):
        artifact = self.artifacts.create(
            self.owner["id"], "plain-note.txt", "Text files use the internal JSON manifest."
        )
        with self.assertRaisesRegex(ValueError, "not supported"):
            self.service.export(self.owner["id"], artifact["id"])


if __name__ == "__main__":
    unittest.main()
