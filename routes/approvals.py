"""Owner-scoped approval records. Positive execution stays disabled until connectors exist."""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from api.dependencies import get_current_user, get_approval_service

router = APIRouter(prefix="/approvals", tags=["approvals"])


class Decision(BaseModel):
    approved: bool


@router.get("")
def approvals(user=Depends(get_current_user), service=Depends(get_approval_service)):
    return service.list_pending(user["id"])


@router.get("/{approval_id}")
def approval_detail(
    approval_id: str,
    user=Depends(get_current_user),
    service=Depends(get_approval_service),
):
    record = service.get_for_user(approval_id, user["id"])
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Approval not found.")
    return record


@router.post("/{approval_id}")
def decide(
    approval_id: str,
    payload: Decision,
    user=Depends(get_current_user),
    service=Depends(get_approval_service),
):
    current = service.get_for_user(approval_id, user["id"])
    if not current:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Approval not found.")

    if not payload.approved:
        decision = service.decide(approval_id, user["id"], False)
        return {"approval": decision, "execution": None}

    # There is no connector-aware executor yet. Never resume a legacy host
    # operation from an approval record, even if the owner clicks approve.
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail="Direct server-side actions are disabled. Connector approvals are not yet available.",
    )
