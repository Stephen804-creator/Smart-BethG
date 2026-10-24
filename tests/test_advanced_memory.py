from datetime import datetime, timedelta, timezone

from tests.base import SmartBethGTestCase
from services.auth_service import create_user
from services.memory_service import MemoryService, MAX_CONTEXT_CHARS


class TestAdvancedMemory(SmartBethGTestCase):
    def setUp(self):
        super().setUp()
        self.owner = create_user("memory-owner", "password123")
        self.other = create_user("memory-other", "password123")
        self.service = MemoryService()

    def test_typed_memory_preserves_provenance_and_metadata(self):
        entry = self.service.remember(
            self.owner["id"], "Prefer short technical explanations", memory_type="preference",
            confidence=0.9, source="user_confirmed", source_ref="settings:response-style",
            metadata={"confirmed": True}, title="Response preference",
        )
        self.assertEqual(entry["memory_type"], "preference")
        self.assertEqual(entry["source_ref"], "settings:response-style")
        self.assertEqual(entry["metadata"], {"confirmed": True})
        self.assertAlmostEqual(entry["confidence"], 0.9)

    def test_invalid_type_confidence_and_metadata_are_rejected(self):
        with self.assertRaises(ValueError):
            self.service.remember(self.owner["id"], "fact", memory_type="unknown")
        with self.assertRaises(ValueError):
            self.service.remember(self.owner["id"], "fact", confidence=1.5)
        with self.assertRaises(ValueError):
            self.service.remember(self.owner["id"], "fact", metadata=["not", "an object"])

    def test_expired_memory_remains_reviewable_but_is_not_injected(self):
        expired = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        entry = self.service.remember(self.owner["id"], "expired secret", expires_at=expired)
        self.assertEqual(len(self.service.list_all(self.owner["id"])), 1)
        self.assertNotIn("expired secret", self.service.recall_context(self.owner["id"]))
        self.assertTrue(self.service.forget(self.owner["id"], entry["id"]))

    def test_type_aware_context_prefers_preferences_and_is_bounded(self):
        for index in range(10):
            self.service.remember(self.owner["id"], f"large memory {index}: " + ("x" * 1000))
        self.service.remember(self.owner["id"], "episodic detail", memory_type="episodic")
        self.service.remember(self.owner["id"], "stable preference", memory_type="preference")
        context = self.service.recall_context(self.owner["id"])
        self.assertLessEqual(len(context), MAX_CONTEXT_CHARS + 100)
        self.assertLess(context.index("stable preference"), context.index("episodic detail"))

    def test_scopes_and_owner_isolation_are_preserved(self):
        self.service.remember(self.owner["id"], "private preference", memory_type="preference")
        self.service.remember(self.other["id"], "other person's data", memory_type="semantic")
        self.assertNotIn("other person's data", self.service.recall_context(self.owner["id"]))
        with self.assertRaises(ValueError):
            self.service.remember(self.owner["id"], "missing project", scope="project")

    def test_recall_flags_potentially_conflicting_memories_without_resolving_them(self):
        self.service.remember(self.owner["id"], "The service is available in production", memory_type="semantic")
        self.service.remember(self.owner["id"], "The service is not available in production", memory_type="semantic")
        context = self.service.recall_context(self.owner["id"])
        self.assertIn("Potentially conflicting memories were detected", context)
        self.assertIn("POTENTIAL CONFLICT", context)
        self.assertIn("available in production", context)
        self.assertIn("not available in production", context)
