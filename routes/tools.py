from fastapi import APIRouter,Depends
from api.dependencies import get_current_user,get_controller
router=APIRouter(prefix="/tools",tags=["tools"])
@router.get("")
def tools(user=Depends(get_current_user),controller=Depends(get_controller)): return controller.tool_orchestrator.list_tools()
