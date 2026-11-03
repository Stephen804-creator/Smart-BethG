"""Authenticated owner-scoped provenance timeline API."""
from typing import Any, Literal

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from api.dependencies import get_current_user, get_provenance_service

router = APIRouter(prefix="/provenance", tags=["provenance"])

UserEventType = Literal[
    "source_attached", "ai_contribution", "agent_contribution",
    "human_edit", "transformation", "review", "approval", "rejection",
]


class ProvenanceEventCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_type: UserEventType
    payload: dict[str, Any] = Field(default_factory=dict)


@router.get("/artifacts/{artifact_id}/events")
def list_artifact_events(
    artifact_id: int,
    user=Depends(get_current_user),
    service=Depends(get_provenance_service),
):
    try:
        return service.list_timeline(user["id"], artifact_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="Artifact not found.")


@router.post("/artifacts/{artifact_id}/events", status_code=201)
def append_artifact_event(
    artifact_id: int,
    payload: ProvenanceEventCreate,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key", max_length=200),
    user=Depends(get_current_user),
    service=Depends(get_provenance_service),
):
    try:
        event = service.append_user_event(
            user, artifact_id, payload.event_type, payload.payload, idempotency_key
        )
        event = dict(event)
        import json
        event["payload"] = json.loads(event.pop("payload_json"))
        return event
    except LookupError:
        raise HTTPException(status_code=404, detail="Artifact not found.")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
