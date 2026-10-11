import os
import unittest
import uuid

from database import get_connection, initialize_database
from repositories.conversation_repository import ConversationRepository
from repositories.knowledge_repository import KnowledgeRepository
from repositories.memory_repository import MemoryRepository
from services.auth_service import create_user
from services.sniper_memory import SniperMemoryService


@unittest.skipUnless(
    os.getenv("SMART_BETHG_RUN_POSTGRES_TESTS") == "1",
    "Requires the dedicated PostgreSQL integration-test job",
)
class TestPostgresSniperMemory(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        initialize_database()

    def test_full_text_retrieval_and_context_compilation(self):
        suffix = uuid.uuid4().hex[:10]
        user = create_user("pg-sniper-" + suffix, "test-password-123")
        other = create_user("pg-sniper-other-" + suffix, "test-password-123")
        uid = user["id"]

        memories = MemoryRepository()
        memories.create(
            uid, "Production database decision: PostgreSQL is required.",
            scope="project", scope_ref="smart-bethg",
        )
        memories.create(
            other["id"], "Private database secret: cobalt-fox.",
            scope="user",
        )

        conversations = ConversationRepository()
        conversation_id = conversations.create(uid, "SniperMemory integration")
        conversations.add_message(
            conversation_id, "user",
            "We decided PostgreSQL is the production database for Smart BethG.",
        )
        conversations.add_message(conversation_id, "assistant", "Recorded.")
        for index in range(9):
            conversations.add_message(
                conversation_id, "user", f"Unrelated topic about weather number {index}."
            )

        conn = get_connection()
        try:
            cursor = conn.execute(
                "INSERT INTO files(user_id, filename, path, file_type, source, status) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (uid, "design.txt", "/tmp/design.txt", "text/plain", "test", "stored"),
            )
            conn.commit()
            file_id = cursor.lastrowid
        finally:
            conn.close()
        KnowledgeRepository().create_chunk(
            uid, file_id, "smart-bethg", 0,
            "SniperMemory uses PostgreSQL full-text search to find relevant context.",
        )

        result = SniperMemoryService().compile(
            uid,
            "Which PostgreSQL database choice did we make for production?",
            conversation_id=conversation_id,
            workspace="smart-bethg",
        )
        self.assertIn("PostgreSQL is required", result["context"])
        self.assertIn("full-text search", result["context"])
        self.assertNotIn("cobalt-fox", result["context"])
        self.assertLessEqual(result["stats"]["recent_messages_sent"], 8)
        self.assertGreaterEqual(result["stats"]["relevant_older_turns"], 1)


if __name__ == "__main__":
    unittest.main()
