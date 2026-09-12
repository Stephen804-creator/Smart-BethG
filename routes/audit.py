from fastapi import APIRouter,Depends
from api.dependencies import get_current_user,get_audit_service
router=APIRouter(prefix="/audit",tags=["audit"])
@router.get("")
def audit(user=Depends(get_current_user),service=Depends(get_audit_service)): return service.list_events(user["id"])
