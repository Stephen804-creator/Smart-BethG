import os
import shutil
import tempfile
from unittest.mock import patch

import config
from tests.base import SmartBethGTestCase
from services.auth_service import create_user
from services.file_service import FileService
from services.knowledge_service import KnowledgeService, chunk_text
from providers.provider_manager import provider_manager


class TestKnowledgeRetrievalQuality(SmartBethGTestCase):
    def setUp(self):
        super().setUp()
        self.tmp = tempfile.mkdtemp(prefix="sbg_retrieval_")
        self.original_uploads = config.STORAGE_DIRS["uploads"]
        config.STORAGE_DIRS["uploads"] = self.tmp
        self.owner = create_user("retrieval-owner", "password123")
        self.files = FileService()
        self.knowledge = KnowledgeService(file_service=self.files)

    def tearDown(self):
        config.STORAGE_DIRS["uploads"] = self.original_uploads
        shutil.rmtree(self.tmp, ignore_errors=True)
        super().tearDown()

    def test_chunking_prefers_sentence_boundaries_and_rejects_invalid_bounds(self):
        text = ("First complete sentence. Second complete sentence. Third complete sentence. " * 8)
        chunks = chunk_text(text, chunk_size=100, overlap=10)
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(chunk) <= 100 for chunk in chunks))
        with self.assertRaises(ValueError):
            chunk_text("text", chunk_size=10, overlap=10)

    def test_search_returns_source_citation_and_method(self):
        record = self.files.save_upload(
            self.owner["id"], "refund-policy.txt",
            b"Refunds are available within fourteen days after purchase. Contact support for help.",
        )
        with patch.object(provider_manager, "embedding_provider_name", return_value=None):
            self.knowledge.ingest_file(self.owner["id"], record["id"])
            results = self.knowledge.search(self.owner["id"], "refunds within fourteen days")
        self.assertTrue(results)
        self.assertEqual(results[0]["retrieval_method"], "keyword")
        self.assertIn("refund-policy.txt", results[0]["citation"])
        self.assertGreater(results[0]["relevance_score"], 0)

    def test_reindex_replaces_old_chunks_for_same_file(self):
        record = self.files.save_upload(self.owner["id"], "notes.txt", b"old obsolete content")
        with patch.object(provider_manager, "embedding_provider_name", return_value=None):
            self.knowledge.ingest_file(self.owner["id"], record["id"])
            self.files.storage.put_bytes("uploads", self.owner["id"], os.path.basename(record["path"]), b"new current content")
            self.knowledge.ingest_file(self.owner["id"], record["id"])
            old_results = self.knowledge.search(self.owner["id"], "old obsolete")
            new_results = self.knowledge.search(self.owner["id"], "new current")
        self.assertEqual(old_results, [])
        self.assertTrue(new_results)

    def test_knowledge_recall_labels_uploaded_content_as_evidence(self):
        record = self.files.save_upload(self.owner["id"], "facts.txt", b"The device warranty lasts two years.")
        with patch.object(provider_manager, "embedding_provider_name", return_value=None):
            self.knowledge.ingest_file(self.owner["id"], record["id"])
            context = self.knowledge.recall_context(self.owner["id"], "device warranty")
        self.assertIn("Source 1", context)
        self.assertIn("facts.txt", context)
        self.assertIn("not independently verified facts", context)
