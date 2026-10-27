"""Restricted execution API. No arbitrary host commands or caller-selected images."""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from api.dependencies import get_current_user
from services.sandbox_service import SandboxService, SandboxUnavailableError

router = APIRouter(prefix="/sandbox", tags=["sandbox"])


class PythonExecutionInput(BaseModel):
    source: str = Field(min_length=1, max_length=64000)
    workspace_id: int | None = Field(default=None, ge=1)


@router.post("/python")
def execute_python(payload: PythonExecutionInput, user=Depends(get_current_user)):
    try:
        return SandboxService().execute_python(user["id"], payload.source, payload.workspace_id)
    except SandboxUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/runs")
def list_runs(limit: int = Query(default=50, ge=1, le=100), user=Depends(get_current_user)):
    return {"runs": SandboxService().list_for_user(user["id"], limit)}
