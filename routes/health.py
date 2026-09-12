from fastapi import APIRouter
from datetime import datetime, timezone
router=APIRouter(tags=["health"])
@router.get("/health")
def health(): return {"status":"ok","service":"Smart BethG","timestamp":datetime.now(timezone.utc).isoformat()}
