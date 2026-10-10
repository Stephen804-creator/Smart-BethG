import shutil
import tempfile
import unittest

import config
from tests.base import SmartBethGTestCase
from services.auth_service import create_user
from services.file_service import FileService
from services.knowledge_service import KnowledgeService, chunk_text, cosine_similarity


class TestChunking(SmartBethGTestCase):
    def test_empty_text_produces_no_chunks(self):
        self.assertEqual(chunk_text(""), [])
        self.assertEqual(chunk_text("   "), [])

    def test_short_text_produces_one_chunk(self):
        chunks = chunk_text("hello world", chunk_size=800)
        self.assertEqual(chunks, ["hello world"])

    def test_long_text_is_split_with_overlap(self):
        text = "x" * 2000
        chunks = chunk_text(text, chunk_size=800, overlap=100)
        self.assertGreater(len(chunks), 1)
        # Every chunk must fit within the requested size.
        self.assertTrue(all(len(c) <= 800 for c in chunks))

    def test_chunking_covers_the_whole_text(self):
        """
        Every character of the source must appear in some chunk -
        chunking must not silently drop the tail of a document.
        """
        text = "".join(f"word{i} " for i in range(500))
        chunks = chunk_text(text, chunk_size=200, overlap=20)
        recombined = "".join(chunks)
        self.assertIn("word0", recombined)
        self.assertIn("word499", recombined)


class TestCosineSimilarity(unittest.TestCase):
    def test_identical_vectors_are_maximally_similar(self):
        self.assertAlmostEqual(cosine_similarity([1, 2, 3], [1, 2, 3]), 1.0, places=5)

    def test_orthogonal_vectors_have_zero_similarity(self):
        self.assertAlmostEqual(cosine_similarity([1, 0], [0, 1]), 0.0, places=5)

    def test_opposite_vectors_have_negative_similarity(self):
        self.assertAlmostEqual(cosine_similarity([1, 0], [-1, 0]), -1.0, places=5)

    def test_zero_vector_does_not_crash(self):
        self.assertEqual(cosine_similarity([0, 0], [1, 1]), 0.0)


class TestKnowledgeServiceIngestAndSearch(SmartBethGTestCase):
    def setUp(self):
        super().setUp()
        self._tmp = tempfile.mkdtemp(prefix="sbg_knowledge_uploads_")
        self._orig_uploads_dir = config.STORAGE_DIRS["uploads"]
        config.STORAGE_DIRS["uploads"] = self._tmp
        self.user = create_user("alice", "password123")
        self.file_service = FileService()
        self.service = KnowledgeService(file_service=self.file_service)

    def tearDown(self):
        config.STORAGE_DIRS["uploads"] = self._orig_uploads_dir
        shutil.rmtree(self._tmp, ignore_errors=True)
        super().tearDown()

    def test_ingest_creates_chunks_without_embedding_when_unconfigured(self):
        record = self.file_service.save_upload(self.user["id"], "notes.txt", b"The mitochondria is the powerhouse of the cell.")
        result = self.service.ingest_file(self.user["id"], record["id"])
        self.assertEqual(result["chunks_created"], 1)
        self.assertFalse(result["embedded"])

    def test_ingest_unsupported_file_type_raises(self):
        record = self.file_service.save_upload(self.user["id"], "photo.png", b"binary")
        with self.assertRaises(ValueError):
            self.service.ingest_file(self.user["id"], record["id"])

    def test_has_knowledge_reflects_real_state(self):
        self.assertFalse(self.service.has_knowledge(self.user["id"]))
        record = self.file_service.save_upload(self.user["id"], "notes.txt", b"some content")
        self.service.ingest_file(self.user["id"], record["id"])
        self.assertTrue(self.service.has_knowledge(self.user["id"]))

    def test_reingest_replaces_rather_than_duplicates(self):
        record = self.file_service.save_upload(self.user["id"], "notes.txt", b"first version content")
        self.service.ingest_file(self.user["id"], record["id"])
        self.service.ingest_file(self.user["id"], record["id"])
        chunks = self.service.repo.list_for_user(self.user["id"])
        self.assertEqual(len(chunks), 1)

    def test_keyword_fallback_finds_relevant_chunk(self):
        """
        No embedding provider configured in the test environment - this
        exercises the real, honest fallback path, not semantic search.
        """
        record = self.file_service.save_upload(
            self.user["id"], "bio.txt", b"The mitochondria is the powerhouse of the cell."
        )
        self.service.ingest_file(self.user["id"], record["id"])
        results = self.service.search(self.user["id"], "mitochondria")
        self.assertEqual(len(results), 1)
        self.assertIn("mitochondria", results[0]["content"].lower())

    def test_keyword_fallback_returns_nothing_for_unrelated_query(self):
        record = self.file_service.save_upload(self.user["id"], "bio.txt", b"The mitochondria is the powerhouse of the cell.")
        self.service.ingest_file(self.user["id"], record["id"])
        results = self.service.search(self.user["id"], "quantum entanglement particle physics")
        self.assertEqual(results, [])

    def test_keyword_fallback_ignores_punctuation(self):
        """
        A query ending in "?" or a chunk ending in "." must still match
        on the underlying word - the earlier version of this fallback
        compared raw tokens including trailing punctuation and silently
        missed matches like this.
        """
        record = self.file_service.save_upload(self.user["id"], "policy.txt", b"Refunds are issued within 14 days.")
        self.service.ingest_file(self.user["id"], record["id"])
        results = self.service.search(self.user["id"], "what does it say about refunds?")
        self.assertEqual(len(results), 1)

    def test_search_does_not_leak_other_users_knowledge(self):
        other = create_user("bob", "password123")
        record = self.file_service.save_upload(other["id"], "secret.txt", b"the launch codes are hidden here")
        self.service.ingest_file(other["id"], record["id"])
        results = self.service.search(self.user["id"], "launch codes")
        self.assertEqual(results, [])

    def test_recall_context_empty_when_nothing_ingested(self):
        self.assertEqual(self.service.recall_context(self.user["id"], "anything"), "")

    def test_recall_context_includes_matched_content(self):
        record = self.file_service.save_upload(self.user["id"], "bio.txt", b"The mitochondria is the powerhouse of the cell.")
        self.service.ingest_file(self.user["id"], record["id"])
        context = self.service.recall_context(self.user["id"], "mitochondria")
        self.assertIn("mitochondria", context.lower())
        self.assertIn("uploaded files", context)


class TestKnowledgeGroundsChatEndToEnd(SmartBethGTestCase):
    """
    The point of wiring this into ChatService: ingested file content
    must actually reach the AI provider call, not just sit searchable
    and unused.
    """

    def setUp(self):
        super().setUp()
        self._tmp = tempfile.mkdtemp(prefix="sbg_knowledge_chat_uploads_")
        self._orig_uploads_dir = config.STORAGE_DIRS["uploads"]
        config.STORAGE_DIRS["uploads"] = self._tmp
        self.user = create_user("alice", "password123")

    def tearDown(self):
        config.STORAGE_DIRS["uploads"] = self._orig_uploads_dir
        shutil.rmtree(self._tmp, ignore_errors=True)
        super().tearDown()

    def test_ingested_file_content_reaches_the_provider_call(self):
        from services.file_service import FileService
        from services.chat_service import ChatService
        from providers.provider_manager import provider_manager
        import config as cfg

        file_service = FileService()
        knowledge_service = KnowledgeService(file_service=file_service)
        record = file_service.save_upload(
            self.user["id"], "policy.txt", b"Refunds are only issued within 14 days of purchase."
        )
        knowledge_service.ingest_file(self.user["id"], record["id"])

        class CapturingProvider:
            def generate(self, messages, model=None, **kwargs):
                self.last_messages = messages
                return {"text": "Refunds are available within 14 days.", "input_tokens": 1, "output_tokens": 1}

        fake_provider = CapturingProvider()
        orig_platform = dict(provider_manager.platform)
        orig_default = cfg.DEFAULT_PROVIDER
        provider_manager.platform = {"anthropic": fake_provider}
        cfg.DEFAULT_PROVIDER = ""
        try:
            chat_service = ChatService(knowledge_service=knowledge_service)
            chat_service.send(self.user["id"], "what does it say about refunds?")
        finally:
            provider_manager.platform = orig_platform
            cfg.DEFAULT_PROVIDER = orig_default

        combined = " ".join(m["content"] for m in fake_provider.last_messages)
        self.assertIn("14 days", combined)
