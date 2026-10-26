"""Admin-only operational metrics and bounded diagnostic events."""
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse

from api.dependencies import get_current_user
from database import get_connection
from services.observability_service import metrics_snapshot, prometheus_text

router = APIRouter(prefix="/observability", tags=["observability"])


def _require_admin(user):
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Administrator permission is required.")


@router.get("/metrics")
def metrics(user=Depends(get_current_user)):
    _require_admin(user)
    return PlainTextResponse(prometheus_text(), media_type="text/plain; version=0.0.4; charset=utf-8")


@router.get("/snapshot")
def snapshot(user=Depends(get_current_user)):
    _require_admin(user)
    return metrics_snapshot()


@router.get("/events")
def recent_events(limit: int = Query(default=50, ge=1, le=100), user=Depends(get_current_user)):
    _require_admin(user)
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT id,request_id,event_type,severity,route_template,status_code,duration_ms,metadata_json,created_at "
            "FROM operational_events ORDER BY created_at DESC,id DESC LIMIT ?", (limit,)
        ).fetchall()
        import json
        items = []
        for row in rows:
            item = dict(row)
            try:
                item["metadata"] = json.loads(item.pop("metadata_json") or "{}")
            except (TypeError, json.JSONDecodeError):
                item["metadata"] = {}
                item.pop("metadata_json", None)
            items.append(item)
        return {"events": items}
    finally:
        conn.close()
