"""
Smart BethG - Training Data Exporter (admin-only)

Feeds the "BethG Core" fine-tuning path discussed with the operator:
export real conversation data -> review/clean it yourself -> fine-tune
an open-weight model offline (Unsloth, a rented GPU) -> host it -> add
it back in as a provider, same pattern as Groq/OpenRouter. This export
step is NOT wired to anything that trains automatically - there is no
live retraining loop here, intentionally. Training happens outside this
app, on a schedule the operator controls.

Two honesty-driven filtering rules:
1. Only exchanges where the assistant reply actually came from a real,
   configured AI provider are included (`provider IS NOT NULL AND
   provider != 'agent'`). The honest "not configured" / "could not
   reach the provider" failure messages, and synthesized tool/memory
   exchanges, are excluded - they are not examples of good assistant
   behavior and would actively teach a model to fail or recite
   boilerplate.
2. No username, user_id, or other account identifier is included in the
   export - only message content. This is a privacy-conscious default,
   not a substitute for telling users (e.g. in your terms) that
   conversations may be used to improve the service - that disclosure
   is the operator's responsibility, not something this code can do.
"""
from repositories.training_export_repository import TrainingExportRepository


class TrainingExportService:
    def __init__(self, repo: TrainingExportRepository = None):
        self.repo = repo or TrainingExportRepository()

    def export(self, since=None, until=None, limit=1000):
        """
        Returns a list of {"messages": [{"role": ..., "content": ...}, ...]}
        dicts - one per conversation, in the standard chat fine-tuning
        shape used by most tooling (Unsloth, Hugging Face `trl`, OpenAI's
        own fine-tuning format). Caller decides how to persist this
        (e.g. write to a .jsonl file, one JSON object per line).
        """
        raw_conversations = self.repo.fetch_exportable_messages(since, until, limit)

        examples = []
        for conversation_id, messages in raw_conversations.items():
            cleaned = self._clean_pairing(messages)
            if len(cleaned) >= 2:  # at least one real user->assistant exchange
                examples.append({"messages": cleaned})
        return examples

    @staticmethod
    def _clean_pairing(messages):
        """
        Messages already exclude non-qualifying assistant replies (see
        the repository query), which can leave two user messages back
        to back with no answer between them. Drops a user message that
        has no qualifying assistant reply immediately after it, rather
        than exporting an unanswered question as if it were a complete
        example - best-effort, not a guarantee of perfect pairing. This
        export is a starting point for the review step, not a
        finished, ready-to-train dataset.
        """
        cleaned = []
        for i, msg in enumerate(messages):
            if msg["role"] == "user":
                has_answer = i + 1 < len(messages) and messages[i + 1]["role"] == "assistant"
                if not has_answer:
                    continue
            cleaned.append({"role": msg["role"], "content": msg["content"]})
        return cleaned

    def count_exportable(self, since=None, until=None):
        """A cheap preview count before actually exporting - how many examples would this produce right now?"""
        return len(self.export(since=since, until=until, limit=100000))
