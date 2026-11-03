"""Application service for user-reported provenance lifecycle events."""
import json

from repositories.provenance_contracts import EVENT_TYPES
from repositories.provenance_repository import ProvenanceRepository
from services.artifact_service import ArtifactService


USER_REPORTED_EVENT_TYPES = frozenset({
    "source_attached", "ai_contribution", "agent_contribution",
    "human_edit", "transformation", "review", "approval", "rejection",
})


class ProvenanceService:
    def __init__(self, repository=None, artifact_service=None):
        self.repository = repository or ProvenanceRepository()
        self.artifacts = artifact_service or ArtifactService()

    def append_user_event(self, user, artifact_id, event_type, payload=None, idempotency_key=None):
        if event_type not in USER_REPORTED_EVENT_TYPES or event_type not in EVENT_TYPES:
            raise ValueError("Unsupported user-reported provenance event type.")
        artifact = self.artifacts.get(user["id"], artifact_id)
        if not artifact:
            raise LookupError("Artifact not found.")
        safe_payload = dict(payload or {})
        if event_type == "source_attached":
            source_id = safe_payload.get("source_artifact_id")
            if not isinstance(source_id, int) or isinstance(source_id, bool) or source_id < 1:
                raise ValueError("A valid source_artifact_id is required for a source attachment.")
            if source_id == artifact_id:
                raise ValueError("An asset cannot be attached as its own source.")
            source = self.artifacts.get(user["id"], source_id)
            if not source:
                raise ValueError("Source artifact not found for this user.")
            claimed_hash = safe_payload.pop("source_sha256", None)
            actual_hash = source.get("checksum_sha256")
            if not actual_hash:
                raise ValueError("The source asset has no verified SHA-256 identity.")
            if claimed_hash is not None and claimed_hash != actual_hash:
                raise ValueError("The supplied source hash does not match the stored source asset.")
            safe_payload["source_sha256"] = actual_hash
            relationship = safe_payload.get("relationship", "componentOf")
            if relationship not in {"parentOf", "componentOf"}:
                raise ValueError("Source relationship must be parentOf or componentOf.")
            safe_payload["relationship"] = relationship

        if event_type == "human_edit":
            summary = safe_payload.get("summary")
            if not isinstance(summary, str) or not summary.strip() or len(summary) > 4000:
                raise ValueError("A human edit requires a non-empty attribution summary of at most 4000 characters.")
            include_instruction = safe_payload.pop("include_instruction_text", False)
            instruction_text = safe_payload.get("instruction_text")
            if include_instruction is True:
                if not isinstance(instruction_text, str) or not instruction_text.strip() or len(instruction_text) > 4000:
                    raise ValueError("Explicit instruction inclusion requires text of at most 4000 characters.")
                safe_payload["instruction_text_included"] = True
            else:
                if instruction_text is not None:
                    raise ValueError("Instruction text is private by default; explicitly opt in to include it.")
                safe_payload.pop("instruction_text", None)
                safe_payload["instruction_text_included"] = False

        # Client-submitted attribution is explicitly distinguished from provider-
        # instrumented evidence; provider-boundary evidence is recorded separately.
        safe_payload["attribution_basis"] = "user_supplied"
        return self.repository.append_event(
            user["id"], artifact_id, event_type, "human",
            actor_id=str(user["id"]),
            actor_label=(user.get("username") or "Account owner")[:160],
            payload=safe_payload,
            idempotency_key=idempotency_key,
        )

    def list_timeline(self, user_id, artifact_id):
        artifact = self.artifacts.get(user_id, artifact_id)
        if not artifact:
            raise LookupError("Artifact not found.")
        rows = self.repository.list_events(user_id, artifact_id)
        events = []
        for row in rows:
            item = dict(row)
            try:
                item["payload"] = json.loads(item.pop("payload_json"))
            except (TypeError, ValueError):
                item["payload"] = None
                item.pop("payload_json", None)
            events.append(item)
        return {
            "artifact_id": artifact_id,
            "events": events,
            "integrity": self.repository.verify_chain(user_id, artifact_id),
        }
