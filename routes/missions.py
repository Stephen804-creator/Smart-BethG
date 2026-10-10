"""Authenticated mission lifecycle API (tracking, not a background executor)."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.dependencies import get_current_user, get_mission_service

router = APIRouter(prefix="/missions", tags=["missions"])


class MissionCreate(BaseModel):
    objective: str = Field(min_length=1, max_length=12000)
    priority: str = "normal"
    project_id: int | None = Field(default=None, ge=1)


class RunFinish(BaseModel):
    status: str
    result: dict | list | str | int | float | bool | None = None
    error: str | None = Field(default=None, max_length=4000)


@router.post("")
def create_mission(payload: MissionCreate, user=Depends(get_current_user), service=Depends(get_mission_service)):
    try:
        return service.create(user["id"], payload.objective, payload.priority, payload.project_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("")
def list_missions(user=Depends(get_current_user), service=Depends(get_mission_service)):
    return {"missions": service.list_for_user(user["id"])}


@router.get("/{mission_id}")
def get_mission(mission_id: int, user=Depends(get_current_user), service=Depends(get_mission_service)):
    mission = service.get(user["id"], mission_id)
    if not mission:
        raise HTTPException(status_code=404, detail="Mission not found.")
    return mission


@router.post("/{mission_id}/runs")
def start_mission_run(mission_id: int, user=Depends(get_current_user), service=Depends(get_mission_service)):
    try:
        mission = service.start_run(user["id"], mission_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    if not mission:
        raise HTTPException(status_code=404, detail="Mission not found.")
    return mission


@router.post("/{mission_id}/runs/{run_id}/finish")
def finish_mission_run(
    mission_id: int,
    run_id: int,
    payload: RunFinish,
    user=Depends(get_current_user),
    service=Depends(get_mission_service),
):
    try:
        mission = service.finish_run(
            user["id"], mission_id, run_id, payload.status,
            result=payload.result, error=payload.error,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    if not mission:
        raise HTTPException(status_code=404, detail="Mission or run not found.")
    return mission


@router.post("/{mission_id}/cancel")
def cancel_mission(mission_id: int, user=Depends(get_current_user), service=Depends(get_mission_service)):
    if not service.cancel(user["id"], mission_id):
        raise HTTPException(status_code=404, detail="Mission not found or already terminal.")
    return {"cancelled": True}
