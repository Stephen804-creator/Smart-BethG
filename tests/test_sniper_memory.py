import os
import tempfile
import unittest

from database import get_connection
from repositories.conversation_repository import ConversationRepository
from repositories.knowledge_repository import KnowledgeRepository
from repositories.memory_repository import MemoryRepository
from services.auth_service import create_user
from services.memory_service import MemoryService
from services.sniper_memory import SniperMemoryService, rank_documents, tokenize
from tests.base import SmartBethGTestCase


class TestSniperRanking(unittest.TestCase):
    def test_tokenizer_removes_common_words_but_keeps_technical_terms(self):
        words = tokenize("What is the PostgreSQL database and auth_middleware.py?")
        self.assertIn("postgresql", words)
        self.assertIn("auth_middleware.py", words)
        self.assertNotIn("the", words)

    def test_ranker_prefers_relevant_documents(self):
        docs = [
            {"id": 1, "content": "The project uses SQLite for local tests."},
            {"id": 2, "content": "PostgreSQL is the production database."},
        ]
        results = rank_documents("PostgreSQL production database", docs)
        self.assertEqual(results[0]["id"], 2)
        self.assertGreater(results[0]["_sniper_score"], 0)


class TestSniperMemoryContext(SmartBethGTestCase):
    def setUp(self):
        super().setUp()
        self.user = create_user("sniper_user", "password123")
        self.other = create_user("sniper_other", "password123")
        self.conversations = ConversationRepository()
        self.memories = MemoryRepository()
        self.knowledge = KnowledgeRepository()
        self.service = SniperMemoryService(
            conversation_repo=self.conversations,
            memory_repo=self.memories,
            knowledge_repo=self.knowledge,
        )

    def test_retrieves_relevant_project_state_not_unrelated_project(self):
        self.memories.create(
            self.user["id"], "Production database decision: use PostgreSQL.",
            scope="project", scope_ref="smart-bethg",
        )
        self.memories.create(
            self.user["id"], "The local prototype uses SQLite for isolated tests.",
            scope="project", scope_ref="other-project",
        )
        result = self.service.compile(
            self.user["id"], "What production database did we choose?",
            workspace="smart-bethg",
        )
        self.assertIn("PostgreSQL", result["context"])
        self.assertNotIn("other-project", result["context"])
        self.assertEqual(result["stats"]["retrieval_mode"], "local_bm25_no_embedding")

    def test_never_retrieves_another_users_memory(self):
        self.memories.create(
            self.other["id"], "Secret project codename is cobalt-fox.",
            scope="user",
        )
        result = self.service.compile(self.user["id"], "What is the secret project codename?")
        self.assertNotIn("cobalt-fox", result["context"])

    def test_retrieves_relevant_older_turn_without_sending_full_transcript(self):
        conversation_id = self.conversations.create(self.user["id"], "Architecture decisions")
        self.conversations.add_message(
            conversation_id, "user",
            "Remember this decision: PostgreSQL is the production database for Smart BethG.",
        )
        self.conversations.add_message(
            conversation_id, "assistant", "Understood. I will keep that project decision in context."
        )
        for index in range(8):
            self.conversations.add_message(
                conversation_id, "user" if index % 2 == 0 else "assistant",
                f"Unrelated conversation topic number {index} about gardening and weather.",
            )
        result = self.service.compile(
            self.user["id"], "Which database is the production database?",
            conversation_id=conversation_id,
        )
        sent_text = " ".join(message["content"] for message in result["messages"])
        self.assertNotIn("PostgreSQL is the production database", sent_text)
        self.assertIn("PostgreSQL is the production database", result["context"])
        self.assertLessEqual(result["stats"]["recent_messages"], 8)
        self.assertEqual(result["stats"]["relevant_older_turns"], 1)

    def test_retrieves_matching_uploaded_knowledge_without_embedding(self):
        conn = get_connection()
        try:
            cur = conn.execute(
                "INSERT INTO files(user_id, filename, path, file_type, source, status) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (self.user["id"], "architecture.txt", "/tmp/architecture.txt", "text/plain", "test", "stored"),
            )
            conn.commit()
            file_id = cur.lastrowid
        finally:
            conn.close()
        self.knowledge.create_chunk(
            self.user["id"], file_id, "smart-bethg", 0,
            "SniperMemory uses local keyword ranking before adding optional semantic retrieval.",
        )
        self.knowledge.create_chunk(
            self.user["id"], file_id, "smart-bethg", 1,
            "The gardening calendar lists when to plant tomatoes and water seedlings.",
        )
        result = self.service.compile(
            self.user["id"], "How does SniperMemory retrieve context?",
            workspace="smart-bethg",
        )
        self.assertIn("local keyword ranking", result["context"])
        self.assertNotIn("gardening calendar", result["context"])
        self.assertEqual(result["stats"]["knowledge_chunks_selected"], 1)

    def test_context_has_a_hard_character_limit(self):
        self.memories.create(
            self.user["id"], "PostgreSQL " + ("production database decision " * 400),
            scope="project", scope_ref="smart-bethg",
        )
        service = SniperMemoryService(
            conversation_repo=self.conversations,
            memory_repo=self.memories,
            knowledge_repo=self.knowledge,
            max_context_chars=1000,
        )
        result = service.compile(
            self.user["id"], "PostgreSQL production database decision",
            workspace="smart-bethg",
        )
        self.assertLessEqual(len(result["context"]), 1000)
        self.assertLessEqual(
            result["stats"]["estimated_context_tokens"],
            250,
        )

    def test_recent_messages_are_newest_window_in_chronological_order(self):
        conversation_id = self.conversations.create(self.user["id"])
        for index in range(12):
            self.conversations.add_message(conversation_id, "user", f"message {index}")
        result = self.service.compile(
            self.user["id"], "a new question", conversation_id=conversation_id
        )
        self.assertEqual(len(result["messages"]), 8)
        self.assertEqual(result["messages"][0]["content"], "message 4")
        self.assertEqual(result["messages"][-1]["content"], "message 11")


if __name__ == "__main__":
    unittest.main()
