from tests.base import SmartBethGTestCase
from services.auth_service import create_user
from services.memory_service import MemoryService


class TestMemoryService(SmartBethGTestCase):
    def setUp(self):
        super().setUp()
        self.user = create_user("alice", "password123")
        self.other = create_user("bob", "password123")
        self.service = MemoryService()

    def test_remember_and_list(self):
        self.service.remember(self.user["id"], "I prefer concise answers")
        entries = self.service.list_all(self.user["id"])
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["content"], "I prefer concise answers")
        self.assertEqual(entries[0]["scope"], "user")

    def test_remember_rejects_empty_content(self):
        with self.assertRaises(ValueError):
            self.service.remember(self.user["id"], "   ")

    def test_remember_rejects_unknown_scope(self):
        with self.assertRaises(ValueError):
            self.service.remember(self.user["id"], "hello", scope="galaxy")

    def test_forget_removes_entry(self):
        entry = self.service.remember(self.user["id"], "temp fact")
        self.assertTrue(self.service.forget(self.user["id"], entry["id"]))
        self.assertEqual(self.service.list_all(self.user["id"]), [])

    def test_cannot_forget_someone_elses_memory(self):
        entry = self.service.remember(self.other["id"], "their secret")
        self.assertFalse(self.service.forget(self.user["id"], entry["id"]))
        self.assertEqual(len(self.service.list_all(self.other["id"])), 1)

    def test_forget_all_clears_everything_for_user_only(self):
        self.service.remember(self.user["id"], "fact one")
        self.service.remember(self.user["id"], "fact two")
        self.service.remember(self.other["id"], "unrelated fact")

        count = self.service.forget_all(self.user["id"])
        self.assertEqual(count, 2)
        self.assertEqual(self.service.list_all(self.user["id"]), [])
        self.assertEqual(len(self.service.list_all(self.other["id"])), 1)

    def test_recall_context_empty_when_nothing_remembered(self):
        self.assertEqual(self.service.recall_context(self.user["id"]), "")

    def test_recall_context_includes_user_scope(self):
        self.service.remember(self.user["id"], "I use FastAPI", scope="user")
        context = self.service.recall_context(self.user["id"])
        self.assertIn("I use FastAPI", context)

    def test_recall_context_includes_matching_project_scope_only(self):
        self.service.remember(self.user["id"], "this project uses Postgres", scope="project", scope_ref="proj-a")
        self.service.remember(self.user["id"], "this project uses SQLite", scope="project", scope_ref="proj-b")

        context_a = self.service.recall_context(self.user["id"], workspace="proj-a")
        self.assertIn("Postgres", context_a)
        self.assertNotIn("SQLite", context_a)

    def test_recall_context_includes_matching_conversation_scope_only(self):
        self.service.remember(self.user["id"], "in this thread we're debugging auth", scope="conversation", scope_ref="42")
        self.service.remember(self.user["id"], "in this other thread we're doing something else", scope="conversation", scope_ref="99")

        context = self.service.recall_context(self.user["id"], conversation_id=42)
        self.assertIn("debugging auth", context)
        self.assertNotIn("something else", context)

    def test_recall_context_combines_all_relevant_scopes(self):
        self.service.remember(self.user["id"], "user fact", scope="user")
        self.service.remember(self.user["id"], "project fact", scope="project", scope_ref="proj-a")
        self.service.remember(self.user["id"], "conversation fact", scope="conversation", scope_ref="7")

        context = self.service.recall_context(self.user["id"], workspace="proj-a", conversation_id=7)
        self.assertIn("user fact", context)
        self.assertIn("project fact", context)
        self.assertIn("conversation fact", context)

    def test_recall_context_does_not_leak_other_users_memory(self):
        self.service.remember(self.other["id"], "bob's private preference", scope="user")
        context = self.service.recall_context(self.user["id"])
        self.assertEqual(context, "")
