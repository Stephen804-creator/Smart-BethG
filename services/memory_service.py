"""
Smart BethG - Memory (T0801-T0806)

Three scopes, deliberately collapsed from the original phase list's
four (working/session/user/project): "working memory" (in-flight,
within a single reply) and "session memory" (persists across messages
in one conversation) aren't meaningfully different in a system with no
multi-step reasoning loop yet (see agent/planner.py - plans are single-
step). Building two separate mechanisms for a distinction that doesn't
concretely exist yet would be exactly the kind of premature complexity
this project's own rules warn against. So:

- "conversation" scope (scope_ref = conversation_id) covers both
- "user" scope (scope_ref = None) - persists across all of a user's conversations
- "project" scope (scope_ref = workspace name) - persists across a workspace

Retrieval (T0805) is honest about what it is: it returns everything in
the relevant scopes, not a relevance-ranked/embedding-based search.
That's fine while a user has a handful of memories; it will not scale
to hundreds, and no attempt is made to pretend otherwise.

Governance (T0806): a user can list and delete everything remembered
about them - not optional polish, a real requirement.
"""
from repositories.memory_repository import MemoryRepository
from logging_setup import get_logger

logger = get_logger("task")

MAX_CONTEXT_MEMORIES = 20  # keeps the injected context bounded regardless of history


class MemoryService:
    def __init__(self, repo: MemoryRepository = None):
        self.repo = repo or MemoryRepository()

    def remember(self, user_id, content, scope="user", scope_ref=None, source="explicit"):
        content = (content or "").strip()
        if not content:
            raise ValueError("Memory content must not be empty.")
        if scope not in ("conversation", "user", "project"):
            raise ValueError(f"Unknown memory scope: {scope!r}")
        memory_id = self.repo.create(user_id, content, scope=scope, scope_ref=scope_ref, source=source)
        logger.info("Memory stored: user=%s scope=%s ref=%s memory_id=%s", user_id, scope, scope_ref, memory_id)
        return self.repo.get(memory_id, user_id)

    def list_all(self, user_id):
        """Governance view - every scope, for a user to review what's remembered."""
        return self.repo.list_for_user(user_id)

    def forget(self, user_id, memory_id):
        return self.repo.delete(memory_id, user_id)

    def forget_all(self, user_id):
        count = self.repo.delete_all_for_user(user_id)
        logger.info("All memory cleared for user=%s (%s entries)", user_id, count)
        return count

    def recall_context(self, user_id, workspace="default", conversation_id=None):
        """
        Builds a short text block of everything in scope for this
        request: user-level memory always, project-level memory for the
        current workspace, conversation-level memory for the current
        conversation. Returns "" (not None) when there's nothing to
        recall, so callers can always safely concatenate it.
        """
        entries = []
        entries += self.repo.list_by_scope(user_id, "user")
        entries += self.repo.list_by_scope(user_id, "project", scope_ref=workspace)
        if conversation_id:
            entries += self.repo.list_by_scope(user_id, "conversation", scope_ref=str(conversation_id))

        if not entries:
            return ""

        entries = entries[:MAX_CONTEXT_MEMORIES]
        lines = "\n".join(f"- {e['content']}" for e in entries)
        return f"Things Smart BethG has been asked to remember about this user/context:\n{lines}"
