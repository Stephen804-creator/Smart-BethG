"""Authenticated research records API."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.dependencies import get_current_user, get_research_service

router = APIRouter(prefix="/research", tags=["research"])


class ResearchCreate(BaseModel):
    query: str = Field(min_length=1, max_length=4000)
    summary: str = Field(default="", max_length=50000)
    source_urls: list[str] = Field(default_factory=list, max_length=100)
    mission_id: int | None = Field(default=None, ge=1)


@router.post("")
def create_research(payload: ResearchCreate, user=Depends(get_current_user), service=Depends(get_research_service)):
    try:
        return service.create(user["id"], payload.query, payload.summary, payload.source_urls, payload.mission_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("")
def list_research(user=Depends(get_current_user), service=Depends(get_research_service)):
    return {"items": service.list_for_user(user["id"])}


@router.get("/{research_id}")
def get_research(research_id: int, user=Depends(get_current_user), service=Depends(get_research_service)):
    item = service.get(user["id"], research_id)
    if not item:
        raise HTTPException(status_code=404, detail="Research record not found.")
    return item
