from fastapi import APIRouter, Depends
from api.dependencies import get_current_user,get_agent_service
router=APIRouter(prefix="/agents",tags=["agents"])
@router.get("")
def list_agents(user=Depends(get_current_user),service=Depends(get_agent_service)): return service.list_agents(user["id"])
