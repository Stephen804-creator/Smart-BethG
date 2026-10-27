"""Authenticated APIs for Smart BethG roadmap Units 21-24."""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from api.dependencies import get_current_user, require_role
from services.units_21_24 import (
    CommercialAccountService,
    ExtensionManifestService,
    ScheduledAgentJobService,
    UsageIntelligenceService,
)

router = APIRouter(tags=["units-21-24"])
schedules = ScheduledAgentJobService()
extensions = ExtensionManifestService()
usage = UsageIntelligenceService()
commercial = CommercialAccountService()


class ScheduleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    workflow_id: int = Field(gt=0)
    scheduled_at: str = Field(min_length=10, max_length=80)
    interval_seconds: Optional[int] = Field(default=None, ge=60, le=2592000)
    max_runs: Optional[int] = Field(default=None, ge=1, le=10000)


class ScheduleStatusUpdate(BaseModel):
    status: str = Field(pattern="^(active|paused|cancelled)$")


class ExtensionCreate(BaseModel):
    manifest: Dict[str, Any]


class ExtensionReview(BaseModel):
    status: str = Field(pattern="^(approved|disabled)$")


class PlanAssignment(BaseModel):
    user_id: int = Field(gt=0)
    plan_key: str = Field(pattern="^(free|starter|pro|team)$")
    status: str = Field(default="active", pattern="^(active|past_due|cancelled|suspended)$")


class CreditGrant(BaseModel):
    user_id: int = Field(gt=0)
    credits: int = Field(gt=0, le=1000000)
    reason: str = Field(min_length=1, max_length=120)
    idempotency_key: str = Field(min_length=1, max_length=200)


class CreditConsume(BaseModel):
    credits: int = Field(gt=0, le=1000000)
    reason: str = Field(min_length=1, max_length=120)
    idempotency_key: str = Field(min_length=1, max_length=200)


class RewardRequest(BaseModel):
    reward_key: str = Field(min_length=2, max_length=63)
    credits: int = Field(gt=0, le=100000)
    idempotency_key: str = Field(min_length=1, max_length=200)


class RewardReview(BaseModel):
    decision: str = Field(pattern="^(approved|rejected)$")


@router.post("/scheduled-jobs", status_code=201)
def create_schedule(payload: ScheduleCreate, user=Depends(get_current_user)):
    try:
        return schedules.create(
            user["id"], payload.name, payload.workflow_id, payload.scheduled_at,
            payload.interval_seconds, payload.max_runs,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/scheduled-jobs")
def list_schedules(limit: int = Query(default=50, ge=1, le=100), user=Depends(get_current_user)):
    return {"items": schedules.list_for_user(user["id"], limit)}


@router.patch("/scheduled-jobs/{schedule_id}")
def update_schedule(schedule_id: int, payload: ScheduleStatusUpdate, user=Depends(get_current_user)):
    try:
        result = schedules.set_status(user["id"], schedule_id, payload.status)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    if result is None:
        raise HTTPException(status_code=404, detail="Scheduled job not found.")
    return result


@router.post("/extensions", status_code=201)
def create_extension(payload: ExtensionCreate, user=Depends(get_current_user)):
    try:
        return extensions.create(user["id"], payload.manifest)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/extensions")
def list_extensions(user=Depends(get_current_user)):
    return {"items": extensions.list_for_user(user["id"])}


@router.post("/extensions/{extension_id}/review")
def review_extension(extension_id: int, payload: ExtensionReview, admin=Depends(require_role("admin"))):
    if not extensions.review(extension_id, payload.status):
        raise HTTPException(status_code=404, detail="Extension manifest not found.")
    return {"id": extension_id, "status": payload.status, "reviewed_by": admin["id"]}


@router.get("/usage/summary")
def usage_summary(days: int = Query(default=30, ge=1, le=90), user=Depends(get_current_user)):
    try:
        return usage.summary(user["id"], days)
    except Exception:
        raise HTTPException(status_code=503, detail="Usage analytics are temporarily unavailable.")


@router.get("/commercial/overview")
def commercial_overview(user=Depends(get_current_user)):
    try:
        return commercial.overview(user["id"])
    except Exception:
        raise HTTPException(status_code=503, detail="Account capacity details are temporarily unavailable.")


@router.post("/commercial/plans/assign")
def assign_plan(payload: PlanAssignment, admin=Depends(require_role("admin"))):
    try:
        return commercial.assign_plan(payload.user_id, payload.plan_key, payload.status)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/commercial/credits/grant")
def grant_credits(payload: CreditGrant, admin=Depends(require_role("admin"))):
    try:
        return commercial.grant_credits(
            payload.user_id, payload.credits, payload.reason, payload.idempotency_key,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.post("/commercial/credits/consume")
def consume_credits(payload: CreditConsume, user=Depends(get_current_user)):
    try:
        return commercial.consume_credits(
            user["id"], payload.credits, payload.reason, payload.idempotency_key,
        )
    except ValueError as exc:
        status = 402 if str(exc) == "Insufficient credits." else 409
        raise HTTPException(status_code=status, detail=str(exc))


@router.post("/commercial/rewards", status_code=201)
def request_reward(payload: RewardRequest, user=Depends(get_current_user)):
    try:
        return commercial.request_reward(
            user["id"], payload.reward_key, payload.credits, payload.idempotency_key,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.get("/commercial/rewards/pending")
def pending_rewards(_admin=Depends(require_role("admin"))):
    from database import get_connection
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT id,user_id,reward_key,credits,status,idempotency_key,created_at "
            "FROM reward_events WHERE status='pending' ORDER BY created_at ASC LIMIT 200"
        ).fetchall()
        return {"items": [dict(row) for row in rows]}
    finally:
        conn.close()


@router.post("/commercial/rewards/{reward_id}/review")
def review_reward(reward_id: int, payload: RewardReview, admin=Depends(require_role("admin"))):
    result = commercial.review_reward(admin["id"], reward_id, payload.decision)
    if result is None:
        raise HTTPException(status_code=404, detail="Reward request not found.")
    return result
