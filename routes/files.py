from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from fastapi.responses import Response

import config
from api.dependencies import get_current_user
from services.rate_limiter import check_rate_limit
from services.file_service import FileService

router = APIRouter(prefix="/files", tags=["files"])


def get_file_service():
    return FileService()


@router.post("")
async def upload_file(
    file: UploadFile = File(...),
    user=Depends(get_current_user),
    service: FileService = Depends(get_file_service),
):
    if not check_rate_limit(
        f"upload-user:{user['id']}",
        max_attempts=config.UPLOAD_RATE_LIMIT_MAX_ATTEMPTS,
        window_seconds=config.UPLOAD_RATE_LIMIT_WINDOW_SECONDS,
    ):
        raise HTTPException(status_code=429, detail="Upload rate limit reached. Please wait before uploading again.")

    # Bound the read itself, not only the later service call. Reading the
    # entire upload first would let an oversized request consume unbounded
    # memory before MAX_UPLOAD_SIZE_BYTES could reject it.
    content = await file.read(config.MAX_UPLOAD_SIZE_BYTES + 1)
    if len(content) > config.MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(status_code=413, detail="Uploaded file exceeds the configured size limit.")
    try:
        record = service.save_upload(user["id"], file.filename, content, file.content_type)
    except ValueError as exc:
        raise HTTPException(status_code=413, detail=str(exc))
    if record:
        record.pop("path", None)
    return record


@router.get("")
def list_files(user=Depends(get_current_user), service: FileService = Depends(get_file_service)):
    records = service.list_files(user["id"])
    for record in records:
        record.pop("path", None)
    return {"files": records}


@router.get("/search")
def search_files(q: str = Query(min_length=1, max_length=1000), user=Depends(get_current_user), service: FileService = Depends(get_file_service)):
    if not check_rate_limit(
        f"file-search-user:{user['id']}",
        max_attempts=config.FILE_SEARCH_RATE_LIMIT_MAX_ATTEMPTS,
        window_seconds=config.FILE_SEARCH_RATE_LIMIT_WINDOW_SECONDS,
    ):
        raise HTTPException(status_code=429, detail="File search rate limit reached. Please wait.")
    records = service.search(user["id"], q)
    for record in records:
        record.pop("path", None)
    return {"files": records}


@router.get("/{file_id}/download")
def download_file(file_id: int, user=Depends(get_current_user), service: FileService = Depends(get_file_service)):
    content, record = service.read_bytes(user["id"], file_id)
    if content is None:
        raise HTTPException(status_code=404, detail="File not found.")
    return Response(
        content=content,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{record["filename"]}"',
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/{file_id}/text")
def extract_text(file_id: int, user=Depends(get_current_user), service: FileService = Depends(get_file_service)):
    if not check_rate_limit(
        f"file-extract-user:{user['id']}",
        max_attempts=config.FILE_EXTRACT_RATE_LIMIT_MAX_ATTEMPTS,
        window_seconds=config.FILE_EXTRACT_RATE_LIMIT_WINDOW_SECONDS,
    ):
        raise HTTPException(status_code=429, detail="File extraction rate limit reached. Please wait.")
    text, error = service.extract_text(user["id"], file_id)
    if error and text is None:
        raise HTTPException(status_code=422, detail=error)
    return {"text": text}


@router.get("/{file_id}/summary")
def summarize_file(file_id: int, user=Depends(get_current_user), service: FileService = Depends(get_file_service)):
    if not check_rate_limit(f"file-summary-user:{user['id']}", max_attempts=10, window_seconds=300):
        raise HTTPException(status_code=429, detail="File summarization rate limit reached. Please wait.")
    return service.summarize(user["id"], file_id)


@router.post("/{file_id}/ingest")
def ingest_file(
    file_id: int,
    workspace: str = "default",
    user=Depends(get_current_user),
    service: FileService = Depends(get_file_service),
):
    """
    Adds this file to the user's searchable knowledge base (T0901) -
    a separate, explicit step from uploading, since not every upload is
    meant to become persistent knowledge the AI draws on for every
    future chat.
    """
    if not check_rate_limit(
        f"file-ingest-user:{user['id']}",
        max_attempts=config.FILE_INGEST_RATE_LIMIT_MAX_ATTEMPTS,
        window_seconds=config.FILE_INGEST_RATE_LIMIT_WINDOW_SECONDS,
    ):
        raise HTTPException(status_code=429, detail="File ingestion rate limit reached. Please wait.")
    from services.knowledge_service import KnowledgeService
    knowledge_service = KnowledgeService(file_service=service)
    try:
        return knowledge_service.ingest_file(user["id"], file_id, workspace=workspace)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.delete("/{file_id}")
def delete_file(file_id: int, user=Depends(get_current_user), service: FileService = Depends(get_file_service)):
    deleted = service.delete_file(user["id"], file_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="File not found.")
    return {"deleted": True}
