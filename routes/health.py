from datetime import datetime, timezone

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from services.health_service import check_database, check_providers, check_background_worker

router = APIRouter(tags=["health"])


@router.get("/health")
def health():
    """
    A real health check, not a static "ok": actually queries the
    database and actually inspects which AI providers are usable right
    now. See services/health_service.py for the checks themselves.
    """
    db = check_database()

    payload = {
        "status": "ok" if db["status"] == "ok" else "degraded",
        "service": "Smart BethG",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "dependencies": {
            "database": db,
            "ai_providers": check_providers(),
            "background_worker": check_background_worker(),
        },
    }
    return JSONResponse(status_code=200 if db["status"] == "ok" else 503, content=payload)
