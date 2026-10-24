"""Conservative, explainable conflict signals for memories and retrieved evidence.

This module flags possible disagreement; it never decides which source is true.
"""
import re

_NEGATIONS = {"not", "no", "never", "without", "isnt", "isn't", "arent", "aren't", "wasnt", "wasn't", "werent", "weren't", "doesnt", "doesn't", "dont", "don't", "cannot", "cant", "can't", "false", "failed"}
_STOPWORDS = {"a", "an", "the", "and", "or", "but", "to", "of", "in", "on", "at", "for", "from", "with", "by", "as", "is", "are", "was", "were", "be", "been", "being", "it", "this", "that", "i", "we", "you", "they", "he", "she", "my", "our", "your", "their", "use", "uses", "using", "has", "have", "had", "do", "does", "did", "can", "will"}
_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9._'-]*", re.I)
_NUMBER_RE = re.compile(r"(?<![A-Za-z])[+-]?\d+(?:\.\d+)?%?")


def _features(text):
    raw = [token.casefold().replace("’", "'") for token in _TOKEN_RE.findall(text or "")]
    negated = any(token in _NEGATIONS for token in raw)
    tokens = {token.strip(".'-") for token in raw if token not in _STOPWORDS and len(token.strip(".'-")) > 1}
    numbers = set(_NUMBER_RE.findall(text or ""))
    return tokens, negated, numbers


def pair_conflict_signal(left, right, min_overlap=0.55):
    """Return a conservative conflict signal or None for two text strings."""
    left_tokens, left_negated, left_numbers = _features(left)
    right_tokens, right_negated, right_numbers = _features(right)
    if not left_tokens or not right_tokens:
        return None
    similarity = len(left_tokens & right_tokens) / max(1, len(left_tokens | right_tokens))
    if similarity < min_overlap:
        return None
    if left_negated != right_negated:
        return {"kind": "polarity_difference", "confidence": round(similarity, 3),
                "reason": "Similar wording has different negation/polarity signals."}
    if left_numbers and right_numbers and left_numbers != right_numbers:
        return {"kind": "numeric_difference", "confidence": round(similarity, 3),
                "reason": "Similar wording contains different numeric values."}
    return None


def find_pairwise_conflicts(items, text_key="content", source_key="citation", max_pairs=5):
    """Compare bounded items and return explainable review flags, not verdicts."""
    found = []
    for index, left in enumerate(items or []):
        for right in (items or [])[index + 1:]:
            signal = pair_conflict_signal(left.get(text_key, ""), right.get(text_key, ""))
            if signal:
                found.append({**signal, "left_source": left.get(source_key) or left.get("id"),
                              "right_source": right.get(source_key) or right.get("id")})
            if len(found) >= max_pairs:
                return found
    return found
