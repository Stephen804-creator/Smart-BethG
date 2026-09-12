from fastapi import APIRouter,Depends
from pydantic import BaseModel
from api.dependencies import get_current_user,get_approval_service
router=APIRouter(prefix="/approvals",tags=["approvals"])
class Decision(BaseModel): approved:bool
@router.get("")
def approvals(user=Depends(get_current_user),service=Depends(get_approval_service)): return service.list_pending(user["id"])
@router.post("/{approval_id}")
def decide(approval_id:str,payload:Decision,user=Depends(get_current_user),service=Depends(get_approval_service)): return service.decide(approval_id,user["id"],payload.approved)
