"""Scheduling API for reviewed social content; actual posting needs a configured platform adapter."""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from api.dependencies import get_current_user
from services.social_publishing_service import SocialPublishingService

router = APIRouter(prefix="/social-publishing", tags=["social-publishing"])


class ScheduleInput(BaseModel):
    scheduled_at: str = Field(min_length=20, max_length=50)
    idempotency_key: str = Field(min_length=1, max_length=200)


@router.post("/content/{content_id}/schedule")
def schedule_content(content_id: int, payload: ScheduleInput, user=Depends(get_current_user)):
    try:
        return SocialPublishingService().schedule(user["id"], content_id, payload.scheduled_at, payload.idempotency_key)
    except PermissionError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/schedules")
def list_schedules(limit: int = Query(default=50, ge=1, le=100), user=Depends(get_current_user)):
    return {"schedules": SocialPublishingService().list_for_user(user["id"], limit)}


@router.delete("/schedules/{schedule_id}")
def cancel_schedule(schedule_id: str, user=Depends(get_current_user)):
    if not SocialPublishingService().cancel(user["id"], schedule_id):
        raise HTTPException(status_code=409, detail="Only a scheduled item owned by you can be cancelled.")
    return {"cancelled": True, "id": schedule_id}
