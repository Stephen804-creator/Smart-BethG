"""Authenticated workflow definitions and durable execution history."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.dependencies import get_current_user, get_workflow_service

router = APIRouter(prefix="/workflows", tags=["workflows"])


class WorkflowCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=4000)
    steps: list[dict] = Field(default_factory=list, max_length=50)
    graph: dict | None = None


class WorkflowDuplicate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)


class WorkflowUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=4000)
    steps: list[dict] | None = Field(default=None, max_length=50)
    graph: dict | None = None


@router.post("")
def create_workflow(payload: WorkflowCreate, user=Depends(get_current_user), service=Depends(get_workflow_service)):
    try:
        return service.create(
            user["id"], payload.name, payload.description, payload.steps, graph=payload.graph
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("")
def list_workflows(user=Depends(get_current_user), service=Depends(get_workflow_service)):
    return {"workflows": service.list_for_user(user["id"])}


@router.get("/{workflow_id}")
def get_workflow(workflow_id: int, user=Depends(get_current_user), service=Depends(get_workflow_service)):
    workflow = service.get(user["id"], workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found.")
    return workflow


@router.patch("/{workflow_id}")
def update_workflow(
    workflow_id: int,
    payload: WorkflowUpdate,
    user=Depends(get_current_user),
    service=Depends(get_workflow_service),
):
    fields = payload.model_dump(exclude_unset=True)
    if not fields:
        raise HTTPException(status_code=422, detail="Provide at least one field to update.")
    try:
        workflow = service.update(user["id"], workflow_id, fields)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found.")
    return workflow



@router.post("/{workflow_id}/duplicate")
def duplicate_workflow(
    workflow_id: int,
    payload: WorkflowDuplicate | None = None,
    user=Depends(get_current_user),
    service=Depends(get_workflow_service),
):
    try:
        workflow = service.duplicate(user["id"], workflow_id, payload.name if payload else None)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found.")
    return workflow

@router.post("/{workflow_id}/validate")
def validate_workflow(workflow_id: int, user=Depends(get_current_user), service=Depends(get_workflow_service)):
    try:
        workflow = service.validate(user["id"], workflow_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found.")
    return workflow



@router.post("/{workflow_id}/publish")
def publish_workflow(workflow_id: int, user=Depends(get_current_user), service=Depends(get_workflow_service)):
    try:
        workflow = service.publish(user["id"], workflow_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found.")
    return workflow


@router.get("/{workflow_id}/versions")
def list_workflow_versions(workflow_id: int, user=Depends(get_current_user), service=Depends(get_workflow_service)):
    if not service.get(user["id"], workflow_id):
        raise HTTPException(status_code=404, detail="Workflow not found.")
    return {"versions": service.list_versions(user["id"], workflow_id)}


@router.get("/{workflow_id}/versions/{version}")
def get_workflow_version(
    workflow_id: int,
    version: int,
    user=Depends(get_current_user),
    service=Depends(get_workflow_service),
):
    snapshot = service.get_version(user["id"], workflow_id, version)
    if not snapshot:
        raise HTTPException(status_code=404, detail="Workflow version not found.")
    return snapshot

@router.post("/{workflow_id}/runs")
def start_workflow_run(workflow_id: int, user=Depends(get_current_user), service=Depends(get_workflow_service)):
    try:
        run = service.start_run(user["id"], workflow_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    if not run:
        raise HTTPException(status_code=404, detail="Workflow not found.")
    return run


@router.get("/{workflow_id}/runs")
def list_workflow_runs(workflow_id: int, user=Depends(get_current_user), service=Depends(get_workflow_service)):
    if not service.get(user["id"], workflow_id):
        raise HTTPException(status_code=404, detail="Workflow not found.")
    return {"runs": service.list_runs(user["id"], workflow_id)}


@router.get("/runs/{run_id}")
def get_workflow_run(run_id: int, user=Depends(get_current_user), service=Depends(get_workflow_service)):
    run = service.get_run(user["id"], run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Workflow run not found.")
    return run


@router.delete("/{workflow_id}")
def archive_workflow(workflow_id: int, user=Depends(get_current_user), service=Depends(get_workflow_service)):
    if not service.archive(user["id"], workflow_id):
        raise HTTPException(status_code=404, detail="Workflow not found.")
    return {"archived": True}
