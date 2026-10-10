"""User-scoped knowledge ingestion and retrieval with bounded embedding costs."""
import math

import config
from repositories.knowledge_repository import KnowledgeRepository
from services.file_service import FileService
from services.usage_budget_service import UsageBudgetService, BudgetExceededError
from providers.provider_manager import provider_manager
from logging_setup import get_logger

logger = get_logger("task")

CHUNK_SIZE = 800
CHUNK_OVERLAP = 100
DEFAULT_TOP_K = 3


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP):
    """Fixed-size chunking with overlap; intentionally not semantic-boundary aware."""
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
    def __init__(
        self,
        repo: KnowledgeRepository = None,
        file_service: FileService = None,
        budget_service: UsageBudgetService = None,
    ):
        self.repo = repo or KnowledgeRepository()
        self.file_service = file_service or FileService()
        self.budget_service = budget_service or UsageBudgetService()

    def ingest_file(self, user_id, file_id, workspace="default"):
        text, error = self.file_service.extract_text(user_id, file_id)
        if error:
            raise ValueError(error)

        workspace = (workspace or "default").strip()[:100] or "default"
        truncated = len(text) > config.MAX_KNOWLEDGE_CHARS_PER_FILE
        bounded_text = text[:config.MAX_KNOWLEDGE_CHARS_PER_FILE]
        chunks = chunk_text(bounded_text)
        if len(chunks) > config.MAX_KNOWLEDGE_CHUNKS_PER_FILE:
            chunks = chunks[:config.MAX_KNOWLEDGE_CHUNKS_PER_FILE]
            truncated = True

        self.repo.delete_for_file(file_id, user_id)
        if not chunks:
            return {
                "chunks_created": 0, "embedded": False,
                "embedding_status": "empty_file", "truncated": truncated,
            }

        embeddings = [None] * len(chunks)
        embedding_model = None
        embedding_status = "no_embedding_provider"
        provider_name = provider_manager.embedding_provider_name()
        if provider_name:
            provider = provider_manager.get(user_id, provider_name)
            try:
                vectors = []
                for start in range(0, len(chunks), max(1, config.EMBEDDING_BATCH_SIZE)):
                    batch = chunks[start:start + max(1, config.EMBEDDING_BATCH_SIZE)]
                    estimate = self.budget_service.estimate_input_tokens(
                        [{"role": "user", "content": item} for item in batch]
                    )
                    reservation = self.budget_service.reserve(
                        user_id, provider_name, provider.EMBEDDING_MODEL, estimate, 1
                    )
                    try:
                        batch_vectors = provider.embed(batch, task_type="RETRIEVAL_DOCUMENT")
                    except Exception:
                        self.budget_service.mark_failed(reservation["id"])
                        raise
                    try:
                        self.budget_service.reconcile(reservation["id"], estimate, 1)
                    except Exception:
                        logger.exception("Could not reconcile embedding usage; reservation remains conservative")
                    if len(batch_vectors) != len(batch):
                        raise ValueError("Embedding provider returned an unexpected vector count.")
                    vectors.extend(batch_vectors)
                embeddings = vectors
                embedding_model = provider.EMBEDDING_MODEL
                embedding_status = "embedded"
            except BudgetExceededError:
                embeddings = [None] * len(chunks)
                embedding_status = "daily_budget_reached"
                logger.warning("Knowledge ingestion used keyword fallback after budget limit: user=%s file_id=%s", user_id, file_id)
            except Exception as exc:
                embeddings = [None] * len(chunks)
                embedding_status = "embedding_failed"
                logger.warning(
                    "Embedding failed during ingest: user=%s file_id=%s error_type=%s",
                    user_id, file_id, type(exc).__name__,
                )

        for index, chunk in enumerate(chunks):
            self.repo.create_chunk(
                user_id, file_id, workspace, index, chunk, embeddings[index], embedding_model
            )

        logger.info(
            "File ingested: user=%s file_id=%s chunks=%d embedded=%s status=%s truncated=%s",
            user_id, file_id, len(chunks), embedding_model is not None, embedding_status, truncated,
        )
        return {
            "chunks_created": len(chunks),
            "embedded": embedding_model is not None,
            "embedding_status": embedding_status,
            "truncated": truncated,
        }

    def has_knowledge(self, user_id) -> bool:
        return self.repo.count_for_user(user_id) > 0

    def search(self, user_id, query, top_k=DEFAULT_TOP_K):
        query = (query or "").strip()[:1000]
        if not query:
            return []
        top_k = max(1, min(int(top_k), 10))
        chunks = self.repo.list_for_user(user_id)
        if not chunks:
            return []

        provider_name = provider_manager.embedding_provider_name()
        provider = provider_manager.get(user_id, provider_name) if provider_name else None
        current_model = getattr(provider, "EMBEDDING_MODEL", None) if provider else None
        # Vectors from different embedding models are not comparable. Old
        # vectors are ignored until the user re-ingests their files.
        embedded_chunks = [
            chunk for chunk in chunks
            if chunk.get("embedding") and current_model and chunk.get("embedding_model") == current_model
        ]
        if provider and embedded_chunks:
            reservation = None
            try:
                estimate = self.budget_service.estimate_input_tokens([{"role": "user", "content": query}])
                reservation = self.budget_service.reserve(
                    user_id, provider_name, current_model, estimate, 1
                )
                query_embedding = provider.embed([query], task_type="RETRIEVAL_QUERY")[0]
                try:
                    self.budget_service.reconcile(reservation["id"], estimate, 1)
                except Exception:
                    logger.exception("Could not reconcile query embedding usage")
                scored = [
                    (cosine_similarity(query_embedding, chunk["embedding"]), chunk)
                    for chunk in embedded_chunks
                    if len(query_embedding) == len(chunk["embedding"])
                ]
                scored.sort(key=lambda pair: pair[0], reverse=True)
                results = [chunk for score, chunk in scored[:top_k] if score > 0]
                if results:
                    return [self._public_chunk(item) for item in results]
            except BudgetExceededError:
                logger.info("Semantic search fell back to keywords due to usage budget: user=%s", user_id)
            except Exception as exc:
                if reservation:
                    try:
                        self.budget_service.mark_failed(reservation["id"])
                    except Exception:
                        logger.exception("Could not finalize failed query-embedding reservation")
                logger.warning("Embedding search failed; using keyword ranking (error_type=%s)", type(exc).__name__)

        return [self._public_chunk(item) for item in self._keyword_search(chunks, query, top_k)]

    @staticmethod
    def _keyword_search(chunks, query, top_k):
        query_words = KnowledgeService._normalize_words(query)
        if not query_words:
            return []
        scored = []
        for chunk in chunks:
            chunk_words = KnowledgeService._normalize_words(chunk["content"])
            overlap = len(query_words & chunk_words)
            if overlap > 0:
                scored.append((overlap, chunk))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [chunk for score, chunk in scored[:top_k]]

    @staticmethod
    def _normalize_words(text: str) -> set:
        return {
            word.strip(".,!?;:\"'()[]{}")
            for word in text.lower().split()
            if word.strip(".,!?;:\"'()[]{}")
        }

    @staticmethod
    def _public_chunk(chunk):
        return {key: value for key, value in chunk.items() if key not in {"embedding", "embedding_model"}}

    def recall_context(self, user_id, query) -> str:
        results = self.search(user_id, query)
        if not results:
            return ""
        lines = "\n\n".join(
            f"[Excerpt {i + 1} from an uploaded file]: {chunk['content']}"
            for i, chunk in enumerate(results)
        )
        return f"Relevant content from the user's uploaded files:\n\n{lines}"
