"""Low-cardinality request metrics and best-effort durable operational events."""
import json
import re
import threading
import time
from collections import defaultdict

from database import get_connection

_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,80}$")
_LOCK = threading.Lock()
_COUNTS = defaultdict(int)
_DURATION_MS = defaultdict(float)


def request_id(candidate=None):
    import uuid
    if isinstance(candidate, str) and _REQUEST_ID_RE.fullmatch(candidate):
        return candidate
    return uuid.uuid4().hex


def record_request(method, route, status_code, duration_ms):
    route = route if isinstance(route, str) and route.startswith("/") else "unmatched"
    key = (method, route, int(status_code))
    with _LOCK:
        _COUNTS[key] += 1
        _DURATION_MS[(method, route)] += max(0.0, float(duration_ms))


def metrics_snapshot():
    with _LOCK:
        return {
            "requests": [
                {"method": method, "route": route, "status_code": status, "count": count}
                for (method, route, status), count in sorted(_COUNTS.items())
            ],
            "durations": [
                {"method": method, "route": route, "total_duration_ms": round(duration, 2)}
                for (method, route), duration in sorted(_DURATION_MS.items())
            ],
        }


def prometheus_text():
    snapshot = metrics_snapshot()
    lines = [
        "# HELP smart_bethg_http_requests_total Total HTTP requests by method, route template and status.",
        "# TYPE smart_bethg_http_requests_total counter",
        *[
            f'smart_bethg_http_requests_total{{method="{item["method"]}",route="{_label(item["route"])}",status="{item["status_code"]}"}} {item["count"]}'
            for item in snapshot["requests"]
        ],
        "# HELP smart_bethg_http_request_duration_ms_total Sum of observed HTTP request durations in milliseconds.",
        "# TYPE smart_bethg_http_request_duration_ms_total counter",
        *[
            f'smart_bethg_http_request_duration_ms_total{{method="{item["method"]}",route="{_label(item["route"])}"}} {item["total_duration_ms"]}'
            for item in snapshot["durations"]
        ],
    ]
    return "\n".join(lines) + "\n"


def record_operational_event(request_id_value, event_type, severity, route_template,
                             status_code, duration_ms, metadata=None):
    """Persist only error/slow-request metadata; never persist request bodies or query strings."""
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO operational_events(request_id,event_type,severity,route_template,status_code,duration_ms,metadata_json) "
            "VALUES (?,?,?,?,?,?,?)",
            (request_id_value, event_type, severity, route_template, int(status_code),
             max(0, int(duration_ms)), json.dumps(metadata or {}, ensure_ascii=False)[:4000]),
        )
        conn.commit()
    finally:
        conn.close()


def _label(value):
    return str(value).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
