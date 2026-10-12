"""
SniperMemory core — deterministic, CPU-only context selection.

The conversation transcript remains stored as the user's complete history, but
the provider receives only a compact set of recent turns and relevant older
turns. This avoids resending the full timeline on every chat request.

This first integration deliberately needs no embeddings, vector database, GPU,
VRAM, or extra paid model call. It is a foundation, not the complete future
AST/state-graph product: code dependency indexing and structured graph edges
are separate follow-on stages.
"""
from collections import Counter
import math
import re


_TOKEN_RE = re.compile(r"[a-zA-Z0-9_+#.-]{2,}")
_STOP_WORDS = {
    "about", "after", "again", "also", "and", "are", "because", "been",
    "before", "being", "but", "can", "could", "did", "does", "doing",
    "done", "for", "from", "have", "here", "how", "into", "just", "like",
    "more", "most", "much", "need", "not", "now", "only", "other", "our",
    "out", "please", "same", "should", "some", "such", "than", "that",
    "the", "their", "them", "then", "there", "these", "they", "this",
    "those", "through", "very", "want", "was", "were", "what", "when",
    "where", "which", "while", "will", "with", "would", "you", "your",
}


def _tokens(text):
    return [
        token.lower().strip("._+-")
        for token in _TOKEN_RE.findall(str(text or "").lower())
        if len(token.strip("._+-")) >= 2
        and token.lower().strip("._+-") not in _STOP_WORDS
    ]


def _relevance_scores(query, documents):
    """Return simple TF-IDF-like scores without an embedding model."""
    query_terms = set(_tokens(query))
    if not query_terms or not documents:
        return [0.0] * len(documents)

    doc_terms = [Counter(_tokens(doc)) for doc in documents]
    document_frequency = Counter()
    for counts in doc_terms:
        document_frequency.update(set(counts))

    total = len(documents)
    scores = []
    for text, counts in zip(documents, doc_terms):
        if not counts:
            scores.append(0.0)
            continue
        score = 0.0
        for term in query_terms:
            frequency = counts.get(term, 0)
            if not frequency:
                continue
            inverse_frequency = math.log(1.0 + (total + 0.5) / (document_frequency[term] + 0.5))
            score += inverse_frequency * (1.0 + math.log(frequency))
        normalized = score / max(1.0, math.sqrt(len(counts)))
        if str(query).strip() and str(query).strip().lower() in text.lower():
            normalized *= 1.35
        scores.append(normalized)
    return scores


class SniperMemory:
    """Select useful context under a hard character budget."""

    def __init__(
        self,
        recent_turns=4,
        relevant_turns=4,
        max_context_chars=12000,
        max_scan_messages=2000,
    ):
        self.recent_turns = max(1, int(recent_turns))
        self.relevant_turns = max(0, int(relevant_turns))
        self.max_context_chars = max(1000, int(max_context_chars))
        self.max_scan_messages = max(20, int(max_scan_messages))

    @staticmethod
    def _group_turns(messages):
        turns = []
        for message in messages:
            item = {
                "role": message.get("role", "user"),
                "content": str(message.get("content", "")),
            }
            if item["role"] == "user" or not turns:
                turns.append({"messages": [item]})
            else:
                turns[-1]["messages"].append(item)
        for turn in turns:
            turn["text"] = "\n".join(m["content"] for m in turn["messages"])
            turn["chars"] = sum(len(m["content"]) for m in turn["messages"])
        return turns

    def compile(self, messages, query):
        """
        Return selected messages plus transparent retrieval statistics.

        Newest turn is mandatory. Recent turns preserve conversational flow;
        older turns are added only when their content matches the current query.
        Output order remains chronological so the model sees a coherent exchange.
        """
        messages = list(messages or [])[-self.max_scan_messages:]
        if not messages:
            return {
                "messages": [], "available_messages": 0, "selected_messages": 0,
                "available_chars": 0, "selected_chars": 0, "saved_chars": 0,
                "retrieved_older_turns": 0,
            }

        turns = self._group_turns(messages)
        if not turns:
            return {
                "messages": [], "available_messages": 0, "selected_messages": 0,
                "available_chars": 0, "selected_chars": 0, "saved_chars": 0,
                "retrieved_older_turns": 0,
            }

        available_chars = sum(turn["chars"] for turn in turns)
        newest_index = len(turns) - 1
        recent_start = max(0, len(turns) - self.recent_turns)
        recent_indices = list(range(recent_start, len(turns)))
        older_indices = list(range(0, recent_start))
        older_texts = [turns[index]["text"] for index in older_indices]
        older_scores = _relevance_scores(query, older_texts)
        ranked_older = sorted(
            (
                (score, index)
                for score, index in zip(older_scores, older_indices)
                if score > 0
            ),
            key=lambda pair: (pair[0], pair[1]),
            reverse=True,
        )[:self.relevant_turns]

        # The newest user request must never be displaced by retrieved history.
        selected_indices = [newest_index]
        used_chars = turns[newest_index]["chars"]
        budget = self.max_context_chars

        # Preserve recent context in reverse chronological priority; render it
        # chronologically afterward. If a turn does not fit, skip it rather than
        # slicing a statement into a potentially misleading fragment.
        for index in reversed(recent_indices[:-1]):
            size = turns[index]["chars"]
            if used_chars + size <= budget:
                selected_indices.append(index)
                used_chars += size

        retrieved_older = 0
        for _score, index in ranked_older:
            if index in selected_indices:
                continue
            size = turns[index]["chars"]
            if used_chars + size <= budget:
                selected_indices.append(index)
                used_chars += size
                retrieved_older += 1

        selected_indices.sort()
        selected = [
            message
            for index in selected_indices
            for message in turns[index]["messages"]
        ]
        selected_chars = sum(len(message["content"]) for message in selected)
        return {
            "messages": selected,
            "available_messages": len(messages),
            "selected_messages": len(selected),
            "available_chars": available_chars,
            "selected_chars": selected_chars,
            "saved_chars": max(0, available_chars - selected_chars),
            "retrieved_older_turns": retrieved_older,
        }

    @staticmethod
    def rank_memories(entries, query, limit=20):
        """Rank explicit saved memories while keeping their owner/scope intact."""
        entries = list(entries or [])
        if not entries:
            return []
        scores = _relevance_scores(query, [entry.get("content", "") for entry in entries])
        indexed = list(enumerate(zip(scores, entries)))
        indexed.sort(
            key=lambda pair: (
                pair[1][0],
                int(pair[1][1].get("id") or 0),
            ),
            reverse=True,
        )
        relevant = [entry for _index, (_score, entry) in indexed if _score > 0]
        if relevant:
            return relevant[:max(1, int(limit))]
        # If the query does not match, preserve the established newest-first
        # behavior rather than returning an empty memory block.
        return sorted(entries, key=lambda entry: int(entry.get("id") or 0), reverse=True)[:max(1, int(limit))]
