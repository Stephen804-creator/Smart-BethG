"""Approval-gated social publication endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Header
from api.dependencies import get_current_user
from services.social_publishing_service import SocialPublishingService

router = APIRouter(prefix="/social-publishing", tags=["social-publishing"])
service = SocialPublishingService()


@router.get("/publishers")
def publisher_catalog(user=Depends(get_current_user)):
    return {"publishers": service.catalog(),
            "note": "A platform is publishable only when a trusted provider adapter is installed and configured."}


@router.post("/content/{content_id}", status_code=201)
def request_publication(content_id: int, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
                        user=Depends(get_current_user)):
    try:
        result = service.request_publish(user["id"], content_id, idempotency_key)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    if not result:
        raise HTTPException(status_code=404, detail="Social content not found.")
    return result


@router.get("/attempts")
def list_publications(limit: int = 30, user=Depends(get_current_user)):
    return {"attempts": service.list_for_user(user["id"], limit)}


@router.get("/attempts/{attempt_id}")
def get_publication(attempt_id: int, user=Depends(get_current_user)):
    item = service.get_attempt(user["id"], attempt_id)
    if not item:
        raise HTTPException(status_code=404, detail="Publication attempt not found.")
    return item


@router.post("/attempts/{attempt_id}/execute")
def execute_publication(attempt_id: int, user=Depends(get_current_user)):
    try:
        item = service.execute_approved(user["id"], attempt_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    if not item:
        raise HTTPException(status_code=404, detail="Publication attempt not found.")
    return item
