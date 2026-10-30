"""Restricted execution API. No arbitrary host commands or caller-selected images."""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from api.dependencies import get_current_user
from services.runtime_registry import list_runtimes
from services.sandbox_service import SandboxService, SandboxUnavailableError

router = APIRouter(prefix="/sandbox", tags=["sandbox"])


class ExecutionInput(BaseModel):
    runtime_id: str = Field(min_length=1, max_length=40, pattern=r"^[a-z0-9_-]+$")
    source: str = Field(min_length=1, max_length=64000)
    workspace_id: int | None = Field(default=None, ge=1)


class PythonExecutionInput(BaseModel):
    source: str = Field(min_length=1, max_length=64000)
    workspace_id: int | None = Field(default=None, ge=1)


@router.get("/runtimes")
def get_runtimes(user=Depends(get_current_user)):
    # Only operator-registered runtimes are returned. Image references and
    # internal allowlist configuration are never exposed to clients.
    return {"runtimes": list_runtimes()}


@router.post("/execute")
def execute_runtime(payload: ExecutionInput, user=Depends(get_current_user)):
    try:
        return SandboxService().execute_runtime(
            user["id"], payload.runtime_id, payload.source, payload.workspace_id
        )
    except SandboxUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


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
