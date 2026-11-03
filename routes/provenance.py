"""Authenticated owner-scoped provenance timeline API."""
from typing import Any, Literal

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from api.dependencies import (
    get_current_user, get_provenance_service, get_provenance_manifest_service,
)

router = APIRouter(prefix="/provenance", tags=["provenance"])

UserEventType = Literal[
    "source_attached", "ai_contribution", "agent_contribution",
    "human_edit", "transformation", "review", "approval", "rejection",
]


class ProvenanceEventCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_type: UserEventType
    payload: dict[str, Any] = Field(default_factory=dict)


class ManifestVerifyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    manifest_id: int | None = Field(default=None, ge=1)


@router.get("/artifacts/{artifact_id}/manifest")
def get_artifact_manifest(
    artifact_id: int,
    user=Depends(get_current_user),
    service=Depends(get_provenance_manifest_service),
):
    try:
        manifest = service.get_latest_manifest(user["id"], artifact_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="Artifact not found.")
    if not manifest:
        raise HTTPException(status_code=404, detail="Provenance manifest not found.")
    return manifest


@router.post("/artifacts/{artifact_id}/manifest")
def generate_artifact_manifest(
    artifact_id: int,
    user=Depends(get_current_user),
    service=Depends(get_provenance_manifest_service),
):
    try:
        return service.generate_manifest(user["id"], artifact_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="Artifact not found.")
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.post("/artifacts/{artifact_id}/manifest/sign")
def sign_artifact_manifest(
    artifact_id: int,
    user=Depends(get_current_user),
    service=Depends(get_provenance_manifest_service),
):
    try:
        return service.sign_manifest(user["id"], artifact_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="Artifact not found.")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/artifacts/{artifact_id}/manifest/verify")
def verify_artifact_manifest(
    artifact_id: int,
    payload: ManifestVerifyRequest | None = None,
    user=Depends(get_current_user),
    service=Depends(get_provenance_manifest_service),
):
    try:
        return service.verify_manifest(
            user["id"], artifact_id,
            manifest_id=payload.manifest_id if payload else None,
        )
    except LookupError:
        raise HTTPException(status_code=404, detail="Artifact not found.")


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
