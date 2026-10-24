"""Owner-scoped, governed memory with typed records and bounded context retrieval."""
from datetime import datetime, timezone

from repositories.memory_repository import MemoryRepository
from services.conflict_detection import find_pairwise_conflicts
from logging_setup import get_logger

logger = get_logger("task")

MAX_CONTEXT_MEMORIES = 20
MAX_CONTEXT_CHARS = 6000
MEMORY_TYPES = {"episodic", "semantic", "procedural", "preference", "policy", "evidence"}
_TYPE_PRIORITY = {"policy": 0, "preference": 1, "procedural": 2, "semantic": 3, "evidence": 4, "episodic": 5}


class MemoryService:
    def __init__(self, repo: MemoryRepository = None):
        self.repo = repo or MemoryRepository()

    def remember(self, user_id, content, scope="user", scope_ref=None, source="explicit",
                 memory_type="episodic", confidence=1.0, source_ref=None, metadata=None,
                 expires_at=None, title=None):
        content = (content or "").strip()
        if not content:
            raise ValueError("Memory content must not be empty.")
        if scope not in ("conversation", "user", "project"):
            raise ValueError(f"Unknown memory scope: {scope!r}")
        if memory_type not in MEMORY_TYPES:
            raise ValueError(f"Unknown memory type: {memory_type!r}")
        try:
            confidence = float(confidence)
        except (TypeError, ValueError) as exc:
            raise ValueError("Memory confidence must be a number between 0 and 1.") from exc
        if not 0 <= confidence <= 1:
            raise ValueError("Memory confidence must be between 0 and 1.")
        if metadata is not None and not isinstance(metadata, dict):
            raise ValueError("Memory metadata must be an object.")
        if len(content) > 12000:
            raise ValueError("Memory content exceeds the 12000-character limit.")
        if source_ref is not None and len(str(source_ref)) > 1000:
            raise ValueError("Memory source reference exceeds the 1000-character limit.")
        if expires_at:
            try:
                parsed = datetime.fromisoformat(str(expires_at).replace("Z", "+00:00"))
            except ValueError as exc:
                raise ValueError("Memory expiry must be an ISO-8601 timestamp.") from exc
            if parsed.tzinfo is None:
                raise ValueError("Memory expiry must include a timezone.")
            expires_at = parsed.astimezone(timezone.utc).isoformat()
        if scope in {"conversation", "project"} and not scope_ref:
            raise ValueError(f"{scope.title()} memory requires a scope reference.")
        memory_id = self.repo.create(
            user_id, content, scope=scope, scope_ref=str(scope_ref) if scope_ref is not None else None,
            source=source, memory_type=memory_type, confidence=confidence,
            source_ref=source_ref, metadata=metadata, expires_at=expires_at, title=title,
        )
        logger.info("Memory stored: user=%s scope=%s type=%s memory_id=%s", user_id, scope, memory_type, memory_id)
        return self.repo.get(memory_id, user_id)

    def list_all(self, user_id):
        """Governance view: all records, including expired records for user review."""
        return self.repo.list_for_user(user_id)

    def forget(self, user_id, memory_id):
        return self.repo.delete(memory_id, user_id)

    def forget_all(self, user_id):
        count = self.repo.delete_all_for_user(user_id)
        logger.info("All memory cleared for user=%s (%s entries)", user_id, count)
        return count

    @staticmethod
    def _is_active(entry, now):
        expiry = entry.get("expires_at")
        if not expiry:
            return True
        try:
            parsed = datetime.fromisoformat(str(expiry).replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc) > now
        except (TypeError, ValueError):
            # Malformed expiry metadata fails closed for context injection.
            return False

    def recall_context(self, user_id, workspace="default", conversation_id=None):
        """Return relevant scopes in a bounded, type-aware block; never cross owners."""
        entries = list(self.repo.list_by_scope(user_id, "user"))
        if workspace:
            entries.extend(self.repo.list_by_scope(user_id, "project", scope_ref=str(workspace)))
        if conversation_id is not None:
            entries.extend(self.repo.list_by_scope(user_id, "conversation", scope_ref=str(conversation_id)))
        now = datetime.now(timezone.utc)
        entries = [entry for entry in entries if self._is_active(entry, now)]
        entries.sort(key=lambda item: (
            _TYPE_PRIORITY.get(item.get("memory_type", "episodic"), 99),
            -int(item.get("id") or 0),
        ))
        if not entries:
            return ""
        conflicts = find_pairwise_conflicts(entries, text_key="content", source_key="id")
        conflict_ids = {str(value) for item in conflicts for value in (item.get("left_source"), item.get("right_source"))}
        lines = []
        used = 0
        for entry in entries[:MAX_CONTEXT_MEMORIES]:
            content = (entry.get("content") or "").strip()
            if not content:
                continue
            label = entry.get("memory_type", "episodic")
            conflict_marker = " [POTENTIAL CONFLICT — review sources]" if str(entry.get("id")) in conflict_ids else ""
            line = f"- [{label}; confidence={float(entry.get('confidence', 1.0)):.2f}]{conflict_marker} {content}"
            remaining = MAX_CONTEXT_CHARS - used
            if remaining <= 0:
                break
            if len(line) > remaining:
                if remaining < 80:
                    break
                line = line[:remaining - 1] + "…"
            lines.append(line)
            used += len(line) + 1
        if not lines:
            return ""
        header = "Things Smart BethG has been asked to remember about this user/context:"
        if conflicts:
            header += " Potentially conflicting memories were detected; preserve both and ask the user or consult their sources rather than silently choosing one."
        return header + "\n" + "\n".join(lines)
