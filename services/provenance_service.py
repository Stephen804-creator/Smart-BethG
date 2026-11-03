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
        # Client-submitted attribution is explicitly distinguished from provider-
        # instrumented evidence; Unit 4 adds trusted execution-boundary events.
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
