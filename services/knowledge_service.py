"""
Smart BethG - Knowledge Base (T0901-T0904)

Ingests an already-uploaded file (see services/file_service.py) into
searchable chunks. Retrieval is real semantic search when an
embedding-capable provider (OpenAI or Google - Anthropic has no
embeddings API) is configured, computed with plain cosine similarity in
Python - no vector database, which is honest and fine at the scale of
one user's own files, and would need replacing before it scaled to a
shared knowledge base across many users.

When no embedding provider is configured, search falls back to a real
keyword-overlap ranking rather than refusing outright - it is
explicitly NOT semantic search in that case, and is documented as such
everywhere it's surfaced.

Files aren't workspace-scoped in this system (see files table), so
knowledge search deliberately isn't either - it searches everything the
user has ingested, not just the current workspace's files.
"""
import math

from repositories.knowledge_repository import KnowledgeRepository
from services.file_service import FileService
from providers.provider_manager import provider_manager
from logging_setup import get_logger

logger = get_logger("task")

CHUNK_SIZE = 800
CHUNK_OVERLAP = 100
DEFAULT_TOP_K = 3


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP):
    """Fixed-size chunking with overlap - simple and honest, not sentence/semantic-boundary aware."""
    text = text or ""
    if not text.strip():
        return []
    chunks = []
    start = 0
    n = len(text)
    while start < n:
        end = min(start + chunk_size, n)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end == n:
            break
        start = end - overlap
    return chunks


def cosine_similarity(a, b) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


class KnowledgeService:
    def __init__(self, repo: KnowledgeRepository = None, file_service: FileService = None):
        self.repo = repo or KnowledgeRepository()
        self.file_service = file_service or FileService()

    def ingest_file(self, user_id, file_id, workspace="default"):
        text, error = self.file_service.extract_text(user_id, file_id)
        if error:
            raise ValueError(error)

        self.repo.delete_for_file(file_id, user_id)  # re-ingesting replaces, doesn't duplicate

        chunks = chunk_text(text)
        if not chunks:
            return {"chunks_created": 0, "embedded": False}

        embeddings = [None] * len(chunks)
        embedding_model = None
        provider_name = provider_manager.embedding_provider_name()
        if provider_name:
            provider = provider_manager.get(user_id, provider_name)
            try:
                embeddings = provider.embed(chunks)
                embedding_model = provider.EMBEDDING_MODEL
            except Exception as exc:
                logger.error("Embedding failed during ingest: user=%s file_id=%s error=%s", user_id, file_id, exc)
                embeddings = [None] * len(chunks)  # stored unembedded - search falls back to keyword ranking

        for i, chunk in enumerate(chunks):
            self.repo.create_chunk(user_id, file_id, workspace, i, chunk, embeddings[i], embedding_model)

        logger.info(
            "File ingested: user=%s file_id=%s chunks=%d embedded=%s",
            user_id, file_id, len(chunks), embedding_model is not None,
        )
        return {"chunks_created": len(chunks), "embedded": embedding_model is not None}

    def has_knowledge(self, user_id) -> bool:
        return self.repo.count_for_user(user_id) > 0

    def search(self, user_id, query, top_k=DEFAULT_TOP_K):
        chunks = self.repo.list_for_user(user_id)
        if not chunks or not (query or "").strip():
            return []

        provider_name = provider_manager.embedding_provider_name()
        embedded_chunks = [c for c in chunks if c["embedding"]]
        if provider_name and embedded_chunks:
            try:
                provider = provider_manager.get(user_id, provider_name)
                query_embedding = provider.embed([query])[0]
                scored = [(cosine_similarity(query_embedding, c["embedding"]), c) for c in embedded_chunks]
                scored.sort(key=lambda pair: pair[0], reverse=True)
                return [c for score, c in scored[:top_k] if score > 0]
            except Exception as exc:
                logger.error("Embedding search failed, falling back to keyword ranking: %s", exc)

        return self._keyword_search(chunks, query, top_k)

    @staticmethod
    def _keyword_search(chunks, query, top_k):
        query_words = KnowledgeService._normalize_words(query)
        if not query_words:
            return []
        scored = []
        for c in chunks:
            chunk_words = KnowledgeService._normalize_words(c["content"])
            overlap = len(query_words & chunk_words)
            if overlap > 0:
                scored.append((overlap, c))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [c for score, c in scored[:top_k]]

    @staticmethod
    def _normalize_words(text: str) -> set:
        """
        Lowercases and strips surrounding punctuation from each word so
        "policy?" matches "policy" and "Refunds" matches "refunds" - a
        keyword fallback that only matches exact untouched tokens would
        miss almost everything a real question asks.
        """
        return {w.strip(".,!?;:\"'()[]{}") for w in text.lower().split() if w.strip(".,!?;:\"'()[]{}")}

    def recall_context(self, user_id, query) -> str:
        """
        Returns "" (not None) when there's nothing relevant, so callers
        can always safely concatenate it - same contract as
        MemoryService.recall_context.
        """
        results = self.search(user_id, query)
        if not results:
            return ""
        lines = "\n\n".join(
            f"[Excerpt {i + 1} from an uploaded file]: {c['content']}" for i, c in enumerate(results)
        )
        return f"Relevant content from the user's uploaded files:\n\n{lines}"
