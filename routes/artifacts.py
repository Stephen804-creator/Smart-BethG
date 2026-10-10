"""Authenticated artifact API."""
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field

from api.dependencies import get_artifact_service, get_current_user

router = APIRouter(prefix="/artifacts", tags=["artifacts"])


class ArtifactCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    content: str = Field(max_length=1024 * 1024)
    artifact_type: str = Field(default="text", max_length=40)
    mission_id: int | None = Field(default=None, ge=1)


@router.post("")
def create_artifact(payload: ArtifactCreate, user=Depends(get_current_user), service=Depends(get_artifact_service)):
    try:
        return service.create(user["id"], payload.name, payload.content, payload.artifact_type, payload.mission_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("")
def list_artifacts(user=Depends(get_current_user), service=Depends(get_artifact_service)):
    return {"artifacts": service.list_for_user(user["id"])}


@router.get("/{artifact_id}")
def get_artifact(artifact_id: int, user=Depends(get_current_user), service=Depends(get_artifact_service)):
    artifact = service.get(user["id"], artifact_id)
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found.")
    artifact.pop("path", None)
    return artifact


@router.get("/{artifact_id}/content")
def read_artifact(artifact_id: int, user=Depends(get_current_user), service=Depends(get_artifact_service)):
    try:
        content, record = service.read_content(user["id"], artifact_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    if content is None:
        raise HTTPException(status_code=404, detail="Artifact not found.")
    return Response(
        content=content,
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=artifact.txt", "X-Content-Type-Options": "nosniff"},
    )


@router.delete("/{artifact_id}")
def delete_artifact(artifact_id: int, user=Depends(get_current_user), service=Depends(get_artifact_service)):
    if not service.delete(user["id"], artifact_id):
        raise HTTPException(status_code=404, detail="Artifact not found.")
    return {"deleted": True}
