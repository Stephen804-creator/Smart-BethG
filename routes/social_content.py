"""Authenticated social-content draft and review API. Publishing integrations are not implied."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.dependencies import get_current_user, get_social_content_service

router = APIRouter(prefix="/social-content", tags=["social-content"])


class SocialContentCreate(BaseModel):
    platform: str = Field(min_length=1, max_length=30)
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=20000)
    hashtags: list[str] = Field(default_factory=list, max_length=30)


class SocialContentUpdate(BaseModel):
    platform: str | None = Field(default=None, min_length=1, max_length=30)
    title: str | None = Field(default=None, min_length=1, max_length=200)
    content: str | None = Field(default=None, min_length=1, max_length=20000)
    hashtags: list[str] | None = Field(default=None, max_length=30)


class StatusChange(BaseModel):
    status: str


@router.post("")
def create_content(payload: SocialContentCreate, user=Depends(get_current_user), service=Depends(get_social_content_service)):
    try:
        return service.create(user["id"], payload.platform, payload.title, payload.content, payload.hashtags)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("")
def list_content(user=Depends(get_current_user), service=Depends(get_social_content_service)):
    return {"items": service.list_for_user(user["id"])}


@router.get("/{content_id}")
def get_content(content_id: int, user=Depends(get_current_user), service=Depends(get_social_content_service)):
    item = service.get(user["id"], content_id)
    if not item:
        raise HTTPException(status_code=404, detail="Social content not found.")
    return item


@router.patch("/{content_id}")
def update_content(
    content_id: int,
    payload: SocialContentUpdate,
    user=Depends(get_current_user),
    service=Depends(get_social_content_service),
):
    fields = payload.model_dump(exclude_unset=True)
    if not fields:
        raise HTTPException(status_code=422, detail="Provide at least one field to update.")
    try:
        item = service.update(user["id"], content_id, fields)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    if not item:
        raise HTTPException(status_code=404, detail="Social content not found.")
    return item


@router.post("/{content_id}/status")
def change_status(
    content_id: int,
    payload: StatusChange,
    user=Depends(get_current_user),
    service=Depends(get_social_content_service),
):
    try:
        item = service.transition(user["id"], content_id, payload.status)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    if not item:
        raise HTTPException(status_code=404, detail="Social content not found.")
    return item
