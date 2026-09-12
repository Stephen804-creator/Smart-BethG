from fastapi import APIRouter, Depends
from pydantic import BaseModel
from api.dependencies import get_current_user,get_controller,get_task_service
router=APIRouter(prefix="/tasks",tags=["tasks"])
class TaskRequest(BaseModel): request:str; workspace:str="default"
@router.post("")
def create_task(payload:TaskRequest,user=Depends(get_current_user),controller=Depends(get_controller)):
    return controller.handle_request(payload.request, user_id=user["id"], workspace=payload.workspace)
@router.get("")
def list_tasks(user=Depends(get_current_user),service=Depends(get_task_service)): return service.list_tasks(user["id"])
