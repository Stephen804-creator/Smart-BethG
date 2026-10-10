from fastapi import APIRouter, Depends

from pydantic import BaseModel, Field

from api.dependencies import get_current_user, get_approval_service, get_tool_service

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
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Approval not found.")
    return record


@router.post("/{approval_id}")
def decide(
    approval_id: str,
    payload: Decision,
    user=Depends(get_current_user),
    service=Depends(get_approval_service),
    tool_service=Depends(get_tool_service),
):
    decision = service.decide(approval_id, user["id"], payload.approved)
    if not payload.approved:
        return {"approval": decision, "execution": None}

    # Approval is bound to the saved operation; execute_approved rechecks the
    # current user's permission and claims the operation atomically.
    execution = tool_service.execute_approved(user, approval_id)
    return {"approval": decision, "execution": execution}
