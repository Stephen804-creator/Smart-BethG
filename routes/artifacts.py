"""Authenticated artifact API."""
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from pydantic import BaseModel, Field

import config
from api.dependencies import get_artifact_service, get_current_user
from services.rate_limiter import check_rate_limit

router = APIRouter(prefix="/artifacts", tags=["artifacts"])


class ArtifactCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    content: str = Field(max_length=1024 * 1024)
    artifact_type: str = Field(default="text", max_length=40)
    mission_id: int | None = Field(default=None, ge=1)


@router.post("")
def create_artifact(payload: ArtifactCreate, user=Depends(get_current_user), service=Depends(get_artifact_service)):
    try:
        artifact = service.create(user["id"], payload.name, payload.content, payload.artifact_type, payload.mission_id)
        artifact.pop("path", None)
        return artifact
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/upload")
async def upload_binary_artifact(
    file: UploadFile = File(...),
    name: str | None = Form(default=None, max_length=160),
    mission_id: int | None = Form(default=None, ge=1),
    user=Depends(get_current_user),
    service=Depends(get_artifact_service),
):
    if not check_rate_limit(
        f"artifact-upload-user:{user['id']}",
        max_attempts=config.UPLOAD_RATE_LIMIT_MAX_ATTEMPTS,
        window_seconds=config.UPLOAD_RATE_LIMIT_WINDOW_SECONDS,
    ):
        raise HTTPException(status_code=429, detail="Artifact upload rate limit reached. Please wait before uploading again.")

    # Read at most the configured cap plus one byte; never buffer an
    # unbounded multipart upload before validating its size.
    try:
        content = await file.read(service.MAX_BINARY_BYTES + 1)
        if len(content) > service.MAX_BINARY_BYTES:
            raise HTTPException(status_code=413, detail="Binary artifact exceeds the 25 MiB limit.")
        artifact = service.create_bytes(
            user["id"], name or file.filename or "artifact",
            content, file.content_type or "application/octet-stream", mission_id,
        )
        artifact.pop("path", None)
        return artifact
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    finally:
        await file.close()


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
        media_type=record.get("content_type") or "text/plain; charset=utf-8",
        headers={
            "Content-Disposition": "attachment; filename*=UTF-8''" + quote(
                record["name"] + {
                    "text": ".txt", "markdown": ".md", "json": ".json",
                    "python": ".py", "javascript": ".js", "html": ".html",
                    "csv": ".csv", "yaml": ".yaml",
                }.get(record.get("artifact_type"), ".txt"),
                safe="",
            ),
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store",
        },
    )


@router.get("/{artifact_id}/download")
def download_artifact(
    artifact_id: int,
    user=Depends(get_current_user),
    service=Depends(get_artifact_service),
):
    try:
        content, record = service.read_bytes(user["id"], artifact_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    if content is None or record is None:
        raise HTTPException(status_code=404, detail="Artifact not found.")
    return Response(
        content=content,
        media_type=record.get("content_type") or "application/octet-stream",
        headers={
            "Content-Disposition": "attachment; filename*=UTF-8''" + quote(record["name"], safe=""),
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store",
        },
    )


@router.delete("/{artifact_id}")
def delete_artifact(artifact_id: int, user=Depends(get_current_user), service=Depends(get_artifact_service)):
    if not service.delete(user["id"], artifact_id):
        raise HTTPException(status_code=404, detail="Artifact not found.")
    return {"deleted": True}
