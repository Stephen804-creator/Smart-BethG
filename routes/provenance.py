"""Authenticated owner-scoped provenance timeline API."""
from typing import Any, Literal

import config

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from api.dependencies import (
    get_current_user, get_provenance_service, get_provenance_manifest_service,
    get_c2pa_export_service,
)
from services.rate_limiter import check_rate_limit

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


@router.get("/c2pa/capabilities")
def c2pa_capabilities(
    user=Depends(get_current_user),
    service=Depends(get_c2pa_export_service),
):
    return service.capabilities()


@router.post("/artifacts/{artifact_id}/c2pa")
def export_c2pa_artifact(
    artifact_id: int,
    user=Depends(get_current_user),
    service=Depends(get_c2pa_export_service),
):
    if not check_rate_limit(
        f"c2pa-export-user:{user['id']}",
        max_attempts=config.C2PA_EXPORT_RATE_LIMIT_MAX_ATTEMPTS,
        window_seconds=config.C2PA_EXPORT_RATE_LIMIT_WINDOW_SECONDS,
    ):
        raise HTTPException(status_code=429, detail="C2PA export rate limit reached.")
    try:
        return service.export(user["id"], artifact_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="Artifact not found.")
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except ValueError as exc:
        message = str(exc)
        status_code = 415 if "not supported" in message.lower() else 422
        raise HTTPException(status_code=status_code, detail=message)


@router.post("/artifacts/{artifact_id}/c2pa/verify")
def verify_c2pa_artifact(
    artifact_id: int,
    user=Depends(get_current_user),
    service=Depends(get_c2pa_export_service),
):
    if not check_rate_limit(
        f"c2pa-verify-user:{user['id']}",
        max_attempts=config.C2PA_VERIFY_RATE_LIMIT_MAX_ATTEMPTS,
        window_seconds=config.C2PA_VERIFY_RATE_LIMIT_WINDOW_SECONDS,
    ):
        raise HTTPException(status_code=429, detail="C2PA verification rate limit reached.")
    try:
        return service.verify_artifact(user["id"], artifact_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="Artifact not found.")
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=415, detail=str(exc))


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
