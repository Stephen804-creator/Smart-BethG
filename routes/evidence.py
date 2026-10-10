"""Authenticated evidence API."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.dependencies import get_current_user, get_evidence_service

router = APIRouter(prefix="/evidence", tags=["evidence"])


class EvidenceCreate(BaseModel):
    claim: str = Field(min_length=1, max_length=10000)
    source_url: str = Field(min_length=1, max_length=2048)
    source_excerpt: str = Field(default="", max_length=20000)
    confidence: float | None = Field(default=None, ge=0, le=1)
    mission_id: int | None = Field(default=None, ge=1)


class EvidenceReview(BaseModel):
    status: str


@router.post("")
def create_evidence(payload: EvidenceCreate, user=Depends(get_current_user), service=Depends(get_evidence_service)):
    try:
        return service.create(
            user["id"], payload.claim, payload.source_url, payload.source_excerpt,
            payload.confidence, payload.mission_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("")
def list_evidence(user=Depends(get_current_user), service=Depends(get_evidence_service)):
    return {"items": service.list_for_user(user["id"])}


@router.get("/{evidence_id}")
def get_evidence(evidence_id: int, user=Depends(get_current_user), service=Depends(get_evidence_service)):
    item = service.get(user["id"], evidence_id)
    if not item:
        raise HTTPException(status_code=404, detail="Evidence not found.")
    return item


@router.post("/{evidence_id}/review")
def review_evidence(
    evidence_id: int,
    payload: EvidenceReview,
    user=Depends(get_current_user),
    service=Depends(get_evidence_service),
):
    try:
        item = service.review(user["id"], evidence_id, payload.status)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    if not item:
        raise HTTPException(status_code=404, detail="Evidence not found.")
    return item
