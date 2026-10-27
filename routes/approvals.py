"""Owner-scoped approvals; only registered connector actions can execute."""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from api.dependencies import get_current_user, get_approval_service, get_connector_action_service

router = APIRouter(prefix="/approvals", tags=["approvals"])

class Decision(BaseModel):
    approved: bool

@router.get("")
def approvals(user=Depends(get_current_user), service=Depends(get_approval_service)):
    return service.list_pending(user["id"])

@router.get("/{approval_id}")
def approval_detail(approval_id: str, user=Depends(get_current_user), service=Depends(get_approval_service)):
    record=service.get_for_user(approval_id,user["id"])
    if not record: raise HTTPException(status_code=404,detail="Approval not found.")
    return record

@router.post("/{approval_id}")
def decide(approval_id: str,payload:Decision,user=Depends(get_current_user),
           service=Depends(get_approval_service),connector_actions=Depends(get_connector_action_service)):
    current=service.get_for_user(approval_id,user["id"])
    if not current: raise HTTPException(status_code=404,detail="Approval not found.")
    if not payload.approved:
        return {"approval":service.decide(approval_id,user["id"],False),"execution":None}
    details=current.get("payload") or {}
    if not all(key in details for key in ("connector_key","installation_id","action","arguments")):
        raise HTTPException(status_code=status.HTTP_410_GONE,
                            detail="Legacy host actions remain disabled; this is not a connector-action approval.")
    decision=service.decide(approval_id,user["id"],True)
    execution=connector_actions.execute_approved(user["id"],approval_id)
    return {"approval":decision,"execution":execution}
