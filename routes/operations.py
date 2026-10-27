"""Admin-only operations telemetry and launch-readiness diagnostics."""
from fastapi import APIRouter, Depends, HTTPException, Query

from api.dependencies import require_role
from services.operations_service import OperationsService

router = APIRouter(prefix="/ops", tags=["operations"])
service = OperationsService()


@router.get("/metrics")
def metrics(hours: int = Query(default=24, ge=1, le=168), _admin=Depends(require_role("admin"))):
    try:
        return service.metrics(hours)
    except Exception:
        raise HTTPException(status_code=503, detail="Operational metrics are temporarily unavailable.")


@router.get("/readiness")
def readiness(_admin=Depends(require_role("admin"))):
    result = service.readiness()
    if result["status"] != "ready":
        raise HTTPException(status_code=503, detail=result)
    return result
