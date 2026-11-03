from tests.base import SmartBethGTestCase
from services.auth_service import create_user
from services.artifact_service import ArtifactService
from repositories.provenance_contracts import canonical_json, sha256_hex, validate_event
from repositories.provenance_repository import ProvenanceRepository


class TestProvenanceContracts(SmartBethGTestCase):
    def test_canonical_json_is_order_independent(self):
        self.assertEqual(canonical_json({"b": 2, "a": 1}), canonical_json({"a": 1, "b": 2}))

    def test_sha256_uses_exact_utf8_bytes(self):
        self.assertEqual(
            sha256_hex("provenance"),
            "96d815328a42cb4ef89d5e0b7a1df6be43b484832c83a7b4596d8402c7c0b12b",
        )

    def test_rejects_unknown_event_and_actor_types(self):
        with self.assertRaises(ValueError):
            validate_event("invented_event", "human")
        with self.assertRaises(ValueError):
            validate_event("asset_created", "invented_actor")

    def test_rejects_secret_fields(self):
        with self.assertRaisesRegex(ValueError, "Sensitive credentials"):
            validate_event("asset_created", "human", {"api_key": "must-not-be-stored"})

    def test_rejects_oversized_or_deep_payload(self):
        with self.assertRaises(ValueError):
            validate_event("asset_created", "human", {"description": "x" * 5000})
        value = {"a": {"b": {"c": {"d": {"e": {"f": {"g": "too deep"}}}}}}}
        with self.assertRaises(ValueError):
            validate_event("asset_created", "human", value)


class TestProvenanceRepository(SmartBethGTestCase):
    def setUp(self):
        super().setUp()
        self.owner = create_user("provenance-owner", "password123")
        self.other = create_user("provenance-other", "password123")
        self.artifact = ArtifactService().create(self.owner["id"], "source", "asset bytes")
        self.repository = ProvenanceRepository()

    def test_appends_ordered_hash_chained_events(self):
        first = self.repository.append_event(
            self.owner["id"], self.artifact["id"], "asset_created", "human",
            payload={"source": "manual"},
        )
        second = self.repository.append_event(
            self.owner["id"], self.artifact["id"], "ai_contribution", "provider",
            provider="openai", model="example-model",
        )
        self.assertEqual((first["sequence_number"], second["sequence_number"]), (1, 2))
        self.assertIsNone(first["previous_event_sha256"])
        self.assertEqual(second["previous_event_sha256"], first["event_sha256"])
        self.assertEqual(len(second["event_sha256"]), 64)

    def test_idempotency_key_returns_existing_event(self):
        first = self.repository.append_event(
            self.owner["id"], self.artifact["id"], "asset_created", "human",
            idempotency_key="upload-once",
        )
        second = self.repository.append_event(
            self.owner["id"], self.artifact["id"], "asset_created", "human",
            idempotency_key="upload-once",
        )
        self.assertEqual(first["id"], second["id"])
        self.assertEqual(len(self.repository.list_events(self.owner["id"], self.artifact["id"])), 1)

    def test_event_lookup_is_owner_scoped(self):
        event = self.repository.append_event(
            self.owner["id"], self.artifact["id"], "asset_created", "human",
        )
        self.assertIsNone(self.repository.get_event(self.other["id"], event["id"]))
        self.assertEqual(self.repository.list_events(self.other["id"], self.artifact["id"]), [])

    def test_cannot_append_to_another_users_artifact(self):
        with self.assertRaisesRegex(ValueError, "Artifact not found"):
            self.repository.append_event(
                self.other["id"], self.artifact["id"], "asset_created", "human",
            )


if __name__ == "__main__":
    import unittest
    unittest.main()
