"""Authenticated bounded code execution; no host-runtime fallback."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.dependencies import get_current_user
from services.sandbox_execution_service import SandboxExecutionService

router = APIRouter(prefix="/sandbox", tags=["sandbox"])
service = SandboxExecutionService()


class PythonExecutionInput(BaseModel):
    source: str = Field(min_length=1, max_length=20000)
    timeout_seconds: int = Field(default=5, ge=1, le=10)


@router.post("/python")
def execute_python(payload: PythonExecutionInput, user=Depends(get_current_user)):
    try:
        return service.execute_python(user["id"], payload.source, payload.timeout_seconds)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/history")
def execution_history(limit: int = 20, user=Depends(get_current_user)):
    return {"executions": service.list_for_user(user["id"], limit)}
