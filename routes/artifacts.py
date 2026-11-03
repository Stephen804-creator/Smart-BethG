"""Authenticated artifact API."""
import os
import tempfile

from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile, File, Form, Header
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


class ArtifactFromChatCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    conversation_id: int = Field(ge=1)
    message_id: int = Field(ge=1)


@router.post("/from-chat", status_code=201)
def create_artifact_from_chat(
    payload: ArtifactFromChatCreate,
    user=Depends(get_current_user),
    service=Depends(get_artifact_service),
):
    try:
        artifact = service.create_from_chat_message(
            user["id"], payload.conversation_id, payload.message_id, payload.name
        )
        artifact.pop("path", None)
        return artifact
    except LookupError:
        raise HTTPException(status_code=404, detail="Chat message not found.")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/upload")
async def upload_binary_artifact(
    file: UploadFile = File(...),
    name: str | None = Form(default=None, max_length=160),
    mission_id: int | None = Form(default=None, ge=1),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    user=Depends(get_current_user),
    service=Depends(get_artifact_service),
):
    if not check_rate_limit(
        f"upload-user:{user['id']}",
        max_attempts=config.UPLOAD_RATE_LIMIT_MAX_ATTEMPTS,
        window_seconds=config.UPLOAD_RATE_LIMIT_WINDOW_SECONDS,
    ):
        raise HTTPException(status_code=429, detail="Upload rate limit reached. Please wait before uploading again.")
    if idempotency_key is not None and len(idempotency_key) > 180:
        raise HTTPException(status_code=422, detail="Idempotency key is too long.")

    temporary_path = None
    size = 0
    try:
        with tempfile.NamedTemporaryFile(prefix="smartbethg-asset-", delete=False) as temporary:
            temporary_path = temporary.name
            while True:
                chunk = await file.read(64 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > config.MAX_ASSET_UPLOAD_BYTES:
                    raise HTTPException(status_code=413, detail="Asset exceeds the configured upload size limit.")
                temporary.write(chunk)
            temporary.flush()
        artifact = service.create_binary_from_path(
            user["id"], name or file.filename or "upload",
            temporary_path, file.content_type, mission_id=mission_id,
            idempotency_key=idempotency_key,
        )
        artifact.pop("path", None)
        return artifact
    except HTTPException:
        raise
    except ValueError as exc:
        status_code = 413 if "size limit" in str(exc).lower() else 422
        raise HTTPException(status_code=status_code, detail=str(exc))
    finally:
        await file.close()
        if temporary_path:
            try:
                os.unlink(temporary_path)
            except OSError:
                pass


@router.post("")
def create_artifact(payload: ArtifactCreate, user=Depends(get_current_user), service=Depends(get_artifact_service)):
    try:
        artifact = service.create(user["id"], payload.name, payload.content, payload.artifact_type, payload.mission_id)
        artifact.pop("path", None)
        return artifact
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
    record = service.get(user["id"], artifact_id)
    if not record:
        raise HTTPException(status_code=404, detail="Artifact not found.")
    if not (record.get("content_type") or "").startswith("text/") and record.get("content_type") != "application/json":
        raise HTTPException(status_code=415, detail="This asset is binary; use the download endpoint.")
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


@router.get("/{artifact_id}/download")
def download_binary_artifact(artifact_id: int, user=Depends(get_current_user), service=Depends(get_artifact_service)):
    try:
        content, record = service.read_bytes(user["id"], artifact_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    if content is None:
        raise HTTPException(status_code=404, detail="Artifact not found or unavailable.")
    return Response(
        content=content,
        media_type=record.get("content_type") or "application/octet-stream",
        headers={
            "Content-Disposition": 'attachment; filename="asset"',
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store",
        },
    )


@router.delete("/{artifact_id}")
def delete_artifact(artifact_id: int, user=Depends(get_current_user), service=Depends(get_artifact_service)):
    if not service.delete(user["id"], artifact_id):
        raise HTTPException(status_code=404, detail="Artifact not found.")
    return {"deleted": True}
