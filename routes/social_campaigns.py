"""Authenticated social campaign planning and schedule API.

These endpoints store a durable schedule. Actual network publishing requires a
connected account and a reviewed, configured platform adapter.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

import json

from api.dependencies import get_current_user, get_artifact_service
from services.social_campaign_service import SocialCampaignService

router = APIRouter(prefix="/social-campaigns", tags=["social-campaigns"])


class CampaignCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    objective: str = Field(min_length=1, max_length=4000)
    platforms: list[str] = Field(min_length=1, max_length=5)
    timezone: str = Field(min_length=1, max_length=80)
    audience: str = Field(default="", max_length=300)
    tone: str = Field(default="clear, helpful", max_length=300)
    reference_urls: list[str] = Field(default_factory=list, max_length=20)
    content_rules: str = Field(default="", max_length=4000)
    start_at: str
    end_at: str | None = None
    cadence: dict = Field(default_factory=dict)
    daily_post_limit: int = Field(default=1, ge=1, le=20)
    autonomy_mode: str = "review_each_post"
    auto_publish_authorized: bool = False


class PlannedPost(BaseModel):
    platform: str = Field(min_length=1, max_length=30)
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=20000)
    hashtags: list[str] = Field(default_factory=list, max_length=30)
    scheduled_at: str


class PlannedPostsBatch(BaseModel):
    posts: list[PlannedPost] = Field(min_length=1, max_length=90)


class CampaignStatusChange(BaseModel):
    status: str


class GeneratePlanRequest(BaseModel):
    count: int = Field(default=30, ge=1, le=30)
    selection: str | None = Field(default=None, max_length=256)


@router.post("")
def create_campaign(payload: CampaignCreate, user=Depends(get_current_user)):
    try:
        return SocialCampaignService().create(
            user["id"], name=payload.name, objective=payload.objective,
            platforms=payload.platforms, timezone_name=payload.timezone,
            audience=payload.audience, tone=payload.tone, reference_urls=payload.reference_urls,
            content_rules=payload.content_rules, start_at=payload.start_at,
            end_at=payload.end_at, cadence=payload.cadence,
            daily_post_limit=payload.daily_post_limit, autonomy_mode=payload.autonomy_mode,
            auto_publish_authorized=payload.auto_publish_authorized,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("")
def list_campaigns(user=Depends(get_current_user)):
    return {"campaigns": SocialCampaignService().list_for_user(user["id"])}


@router.get("/{campaign_id}")
def get_campaign(campaign_id: int, user=Depends(get_current_user)):
    campaign = SocialCampaignService().get(user["id"], campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found.")
    return campaign


@router.post("/{campaign_id}/generate-plan")
def generate_campaign_plan(
    campaign_id: int,
    payload: GeneratePlanRequest,
    user=Depends(get_current_user),
):
    try:
        campaign = SocialCampaignService().generate_plan(
            user["id"], campaign_id, count=payload.count, selection=payload.selection
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found.")
    return campaign


@router.post("/{campaign_id}/posts/{content_id}/approve")
def approve_campaign_post(
    campaign_id: int,
    content_id: int,
    user=Depends(get_current_user),
):
    try:
        campaign = SocialCampaignService().approve_post(user["id"], campaign_id, content_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign or post not found.")
    return campaign


@router.post("/{campaign_id}/posts")
def add_planned_posts(campaign_id: int, payload: PlannedPostsBatch, user=Depends(get_current_user)):
    try:
        campaign = SocialCampaignService().add_posts(
            user["id"], campaign_id, [item.model_dump() for item in payload.posts]
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found.")
    return campaign


@router.post("/{campaign_id}/export-artifact")
def export_campaign_artifact(
    campaign_id: int,
    user=Depends(get_current_user),
    artifacts=Depends(get_artifact_service),
):
    campaign = SocialCampaignService().get(user["id"], campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found.")
    export_data = {
        "schema_version": 1,
        "exported_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        "campaign": {
            "id": campaign["id"],
            "name": campaign["name"],
            "objective": campaign["objective"],
            "audience": campaign["audience"],
            "tone": campaign["tone"],
            "platforms": campaign["platforms"],
            "timezone": campaign["timezone"],
            "start_at": campaign["start_at"],
            "end_at": campaign["end_at"],
            "cadence": campaign["cadence"],
            "status": campaign["status"],
        },
        "posts": campaign["posts"],
    }
    try:
        artifact = artifacts.create(
            user["id"], campaign["name"] + " - content calendar",
            json.dumps(export_data, ensure_ascii=False, indent=2), "json",
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    artifact.pop("path", None)
    return {"artifact": artifact, "message": "Content calendar artifact saved. No social post was published."}


@router.post("/{campaign_id}/status")
def change_campaign_status(campaign_id: int, payload: CampaignStatusChange, user=Depends(get_current_user)):
    try:
        campaign = SocialCampaignService().set_status(user["id"], campaign_id, payload.status)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found.")
    return campaign
