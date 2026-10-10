"""Authenticated project API."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.dependencies import get_current_user, get_project_service

router = APIRouter(prefix="/projects", tags=["projects"])


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=4000)


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=4000)
    status: str | None = None


@router.post("")
def create_project(payload: ProjectCreate, user=Depends(get_current_user), service=Depends(get_project_service)):
    try:
        return service.create(user["id"], payload.name, payload.description)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("")
def list_projects(user=Depends(get_current_user), service=Depends(get_project_service)):
    return {"projects": service.list_for_user(user["id"])}


@router.get("/{project_id}")
def get_project(project_id: int, user=Depends(get_current_user), service=Depends(get_project_service)):
    project = service.get(user["id"], project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")
    return project


@router.patch("/{project_id}")
def update_project(
    project_id: int,
    payload: ProjectUpdate,
    user=Depends(get_current_user),
    service=Depends(get_project_service),
):
    fields = payload.model_dump(exclude_unset=True)
    if not fields:
        raise HTTPException(status_code=422, detail="Provide at least one field to update.")
    try:
        project = service.update(user["id"], project_id, fields)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")
    return project


@router.delete("/{project_id}")
def archive_project(project_id: int, user=Depends(get_current_user), service=Depends(get_project_service)):
    if not service.archive(user["id"], project_id):
        raise HTTPException(status_code=404, detail="Project not found.")
    return {"archived": True}
