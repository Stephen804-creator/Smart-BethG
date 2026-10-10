from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

import config
from api.dependencies import get_current_user, get_controller, get_task_service
from services.rate_limiter import check_rate_limit

router = APIRouter(prefix="/tasks", tags=["tasks"])


class TaskRequest(BaseModel):
    request: str = Field(min_length=1, max_length=config.MAX_CHAT_MESSAGE_CHARS)
    workspace: str = Field(default="default", min_length=1, max_length=100)


@router.post("")
def create_task(
    payload: TaskRequest,
    user=Depends(get_current_user),
    controller=Depends(get_controller),
):
    if not check_rate_limit(
        f"task-user:{user['id']}",
        max_attempts=config.TASK_RATE_LIMIT_MAX_ATTEMPTS,
        window_seconds=config.TASK_RATE_LIMIT_WINDOW_SECONDS,
    ):
        raise HTTPException(status_code=429, detail="Task rate limit reached. Please wait before submitting more work.")
    return controller.handle_request(payload.request, user=user, workspace=payload.workspace)


@router.get("")
def list_tasks(user=Depends(get_current_user), service=Depends(get_task_service)):
    return service.list_tasks(user["id"])
