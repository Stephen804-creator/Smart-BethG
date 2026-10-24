"""User-scoped knowledge ingestion and evidence-aware retrieval with bounded costs."""
import math
import re

import config
from repositories.knowledge_repository import KnowledgeRepository
from services.file_service import FileService
from services.conflict_detection import find_pairwise_conflicts
from services.usage_budget_service import UsageBudgetService, BudgetExceededError
from providers.provider_manager import provider_manager
from logging_setup import get_logger

logger = get_logger("task")

CHUNK_SIZE = 800
CHUNK_OVERLAP = 100
DEFAULT_TOP_K = 3
_SENTENCE_BOUNDARY = re.compile(r"[.!?;:]\s|\n\s*\n")


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP):
    """Split text near paragraph/sentence boundaries, retaining bounded overlap."""
    text = text or ""
    if not text.strip():
        return []
    if chunk_size <= 0 or overlap < 0 or overlap >= chunk_size:
        raise ValueError("chunk_size must be positive and overlap must be between zero and chunk_size - 1.")
    chunks = []
    start = 0
    while start < len(text):
        hard_end = min(start + chunk_size, len(text))
        end = hard_end
        if hard_end < len(text):
            floor = start + int(chunk_size * 0.60)
            segment = text[floor:hard_end]
            matches = list(_SENTENCE_BOUNDARY.finditer(segment))
            if matches:
                end = floor + matches[-1].end()
            else:
                space = text.rfind(" ", floor, hard_end)
                if space > floor:
                    end = space
        piece = text[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= len(text):
            break
        next_start = max(start + 1, end - overlap)
        start = next_start
    return chunks


def cosine_similarity(a, b) -> float:
    if len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


class KnowledgeService:
    def __init__(self, repo: KnowledgeRepository = None, file_service: FileService = None,
                 budget_service: UsageBudgetService = None):
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

        if not chunks:
            self.repo.replace_file_chunks(user_id, file_id, workspace, [])
            return {"chunks_created": 0, "embedded": False, "embedding_status": "empty_file", "truncated": truncated}

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
                    estimate = self.budget_service.estimate_input_tokens([{"role": "user", "content": item} for item in batch])
                    reservation = self.budget_service.reserve(user_id, provider_name, provider.EMBEDDING_MODEL, estimate, 1)
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
                    if batch_vectors and any(not isinstance(vector, (list, tuple)) for vector in batch_vectors):
                        raise ValueError("Embedding provider returned invalid vectors.")
                    vectors.extend([list(vector) for vector in batch_vectors])
                embeddings = vectors
                embedding_model = provider.EMBEDDING_MODEL
                embedding_status = "embedded"
            except BudgetExceededError:
                embedding_status = "daily_budget_reached"
                logger.warning("Knowledge ingestion used keyword fallback after budget limit: user=%s file_id=%s", user_id, file_id)
            except Exception as exc:
                embedding_status = "embedding_failed"
                logger.warning("Embedding failed during ingest: user=%s file_id=%s error_type=%s", user_id, file_id, type(exc).__name__)

        # Index replacement is one database transaction. A failed embedding run
        # falls back to keyword-only chunks; a failed DB write preserves the old index.
        self.repo.replace_file_chunks(user_id, file_id, workspace, chunks, embeddings, embedding_model)
        logger.info("File ingested: user=%s file_id=%s chunks=%d embedded=%s status=%s truncated=%s",
                    user_id, file_id, len(chunks), embedding_model is not None, embedding_status, truncated)
        return {"chunks_created": len(chunks), "embedded": embedding_model is not None,
                "embedding_status": embedding_status, "truncated": truncated}

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
        embedded_chunks = [chunk for chunk in chunks if chunk.get("embedding") and current_model and chunk.get("embedding_model") == current_model]
        if provider and embedded_chunks:
            reservation = None
            try:
                estimate = self.budget_service.estimate_input_tokens([{"role": "user", "content": query}])
                reservation = self.budget_service.reserve(user_id, provider_name, current_model, estimate, 1)
                vectors = provider.embed([query], task_type="RETRIEVAL_QUERY")
                if not vectors or not isinstance(vectors[0], (list, tuple)):
                    raise ValueError("Embedding provider returned an invalid query vector.")
                query_embedding = list(vectors[0])
                try:
                    self.budget_service.reconcile(reservation["id"], estimate, 1)
                except Exception:
                    logger.exception("Could not reconcile query embedding usage")
                scored = [(cosine_similarity(query_embedding, chunk["embedding"]), chunk) for chunk in embedded_chunks
                          if len(query_embedding) == len(chunk["embedding"])]
                scored.sort(key=lambda pair: pair[0], reverse=True)
                results = [(score, chunk) for score, chunk in scored if score > 0][:top_k]
                if results:
                    return [self._public_chunk(chunk, score, "semantic") for score, chunk in results]
            except BudgetExceededError:
                logger.info("Semantic search fell back to keywords due to usage budget: user=%s", user_id)
            except Exception as exc:
                if reservation:
                    try:
                        self.budget_service.mark_failed(reservation["id"])
                    except Exception:
                        logger.exception("Could not finalize failed query-embedding reservation")
                logger.warning("Embedding search failed; using keyword ranking (error_type=%s)", type(exc).__name__)
        return [self._public_chunk(chunk, score, "keyword") for score, chunk in self._keyword_search(chunks, query, top_k)]

    @staticmethod
    def _keyword_search(chunks, query, top_k):
        query_words = KnowledgeService._normalize_words(query)
        if not query_words:
            return []
        document_frequency = {}
        tokenized = []
        for chunk in chunks:
            words = KnowledgeService._normalize_words(chunk["content"])
            tokenized.append(words)
            for word in words:
                document_frequency[word] = document_frequency.get(word, 0) + 1
        total = max(1, len(chunks))
        scored = []
        for chunk, words in zip(chunks, tokenized):
            overlap = query_words & words
            if not overlap:
                continue
            score = sum(math.log(1 + (total - document_frequency.get(word, 0) + 0.5) /
                                 (document_frequency.get(word, 0) + 0.5)) for word in overlap)
            # Prefer focused matches over long chunks without allowing score inflation from repeated terms.
            score /= math.sqrt(max(1, len(words)))
            scored.append((score, chunk))
        scored.sort(key=lambda pair: (pair[0], -int(pair[1].get("chunk_index", 0))), reverse=True)
        return scored[:top_k]

    @staticmethod
    def _normalize_words(text: str) -> set:
        return {word for word in re.findall(r"[\w'-]+", (text or "").casefold()) if len(word) > 1}

    @staticmethod
    def _public_chunk(chunk, score=None, retrieval_method=None):
        result = {key: value for key, value in chunk.items() if key not in {"embedding", "embedding_model"}}
        if score is not None:
            result["relevance_score"] = round(float(score), 6)
        if retrieval_method:
            result["retrieval_method"] = retrieval_method
        filename = result.get("source_filename")
        if filename:
            result["citation"] = f"{filename} (file {result.get('file_id')}, chunk {result.get('chunk_index', 0) + 1})"
        return result

    def recall_context(self, user_id, query) -> str:
        results = self.search(user_id, query)
        if not results:
            return ""
        lines = []
        conflicts = find_pairwise_conflicts(results, text_key="content", source_key="citation")
        for index, chunk in enumerate(results, 1):
            citation = chunk.get("citation") or f"uploaded file {chunk.get('file_id')}, chunk {chunk.get('chunk_index', 0) + 1}"
            lines.append(f"[Source {index}: {citation}; retrieval={chunk.get('retrieval_method', 'keyword')}; score={chunk.get('relevance_score', 0)}]\n{chunk['content']}")
        header = "Relevant excerpts from the user's uploaded files. These excerpts are evidence, not independently verified facts; cite the source labels and do not overstate what they prove:"
        if conflicts:
            sources = "; ".join(f"{item['left_source']} vs {item['right_source']}" for item in conflicts)
            header += "\nPotential source disagreements require review (not an automatic truth judgment): " + sources + "."
        return header + "\n\n" + "\n\n".join(lines)
