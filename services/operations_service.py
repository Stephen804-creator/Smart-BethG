"""Low-cardinality request telemetry, worker liveness, and production readiness gates."""
import json
import logging
import os
from datetime import datetime, timezone

import config
from database import get_connection

logger = logging.getLogger("smart_bethg.operations")


class OperationsService:
    def record_request(self, request_id, method, route, status_code, duration_ms):
        # Store route templates only, never raw query strings, bodies, cookies, or IDs.
        route = (route or "/unmatched")[:300]
        method = (method or "UNKNOWN")[:12]
        try:
            conn = get_connection()
            try:
                conn.execute(
                    "INSERT INTO request_traces(request_id,method,route,status_code,duration_ms) VALUES (?,?,?,?,?)",
                    (request_id, method, route, int(status_code), max(0, int(duration_ms))),
                )
                conn.commit()
            finally:
                conn.close()
        except Exception:
            # Telemetry must never turn a successful request into a failed one.
            logger.warning("Request telemetry write failed", exc_info=True)

    def prune_request_traces(self):
        conn = get_connection()
        try:
            cursor = conn.execute(
                "DELETE FROM request_traces WHERE created_at < CURRENT_TIMESTAMP - INTERVAL '30 days'"
            )
            conn.commit()
            return cursor.rowcount
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def heartbeat_worker(self, worker_id, status="healthy", details=None):
        if status not in {"starting", "healthy", "degraded", "stopping"}:
            raise ValueError("Invalid worker status.")
        conn = get_connection()
        try:
            conn.execute(
                "INSERT INTO worker_heartbeats(worker_id,status,last_seen,details_json) "
                "VALUES (?,?,CURRENT_TIMESTAMP,?) ON CONFLICT(worker_id) DO UPDATE SET "
                "status=EXCLUDED.status,last_seen=CURRENT_TIMESTAMP,details_json=EXCLUDED.details_json",
                (worker_id, status, json.dumps(details or {}, ensure_ascii=False)[:4000]),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def metrics(self, hours=24):
        hours = max(1, min(168, int(hours)))
        conn = get_connection()
        try:
            totals = conn.execute(
                "SELECT COUNT(*) AS requests, "
                "COUNT(*) FILTER (WHERE status_code >= 500) AS server_errors, "
                "COUNT(*) FILTER (WHERE status_code >= 400 AND status_code < 500) AS client_errors, "
                "COALESCE(ROUND(AVG(duration_ms)::numeric,2),0) AS avg_duration_ms, "
                "COALESCE(percentile_cont(0.95) WITHIN GROUP (ORDER BY duration_ms),0) AS p95_duration_ms "
                "FROM request_traces WHERE created_at >= CURRENT_TIMESTAMP - (? * INTERVAL '1 hour')",
                (hours,),
            ).fetchone()
            routes = conn.execute(
                "SELECT route,COUNT(*) AS requests,"
                "COUNT(*) FILTER (WHERE status_code >= 500) AS server_errors,"
                "COALESCE(ROUND(AVG(duration_ms)::numeric,2),0) AS avg_duration_ms "
                "FROM request_traces WHERE created_at >= CURRENT_TIMESTAMP - (? * INTERVAL '1 hour') "
                "GROUP BY route ORDER BY server_errors DESC,requests DESC LIMIT 20",
                (hours,),
            ).fetchall()
            workers = conn.execute(
                "SELECT worker_id,status,last_seen FROM worker_heartbeats "
                "WHERE last_seen >= CURRENT_TIMESTAMP - INTERVAL '2 minutes' ORDER BY last_seen DESC"
            ).fetchall()
            return {"window_hours": hours, "totals": dict(totals),
                    "routes": [dict(row) for row in routes],
                    "workers": [dict(row) for row in workers]}
        finally:
            conn.close()

    def readiness(self):
        checks = {}
        conn = None
        try:
            conn = get_connection()
            conn.execute("SELECT 1")
            version = conn.execute(
                "SELECT version FROM schema_migrations ORDER BY version DESC LIMIT 1"
            ).fetchone()
            checks["database"] = {"status": "ready"}
            checks["migrations"] = {"status": "ready" if version else "not_ready",
                                    "latest": version["version"] if version else None}
            workers = conn.execute(
                "SELECT COUNT(*) AS count FROM worker_heartbeats "
                "WHERE status='healthy' AND last_seen >= CURRENT_TIMESTAMP - INTERVAL '90 seconds'"
            ).fetchone()
            worker_count = int(workers["count"])
            checks["background_worker"] = {
                "status": "ready" if worker_count else "not_ready",
                "healthy_workers": worker_count,
            }
        except Exception:
            logger.warning("Readiness dependency check failed", exc_info=True)
            checks["database"] = {"status": "not_ready"}
            checks["migrations"] = {"status": "not_ready"}
            checks["background_worker"] = {"status": "unknown"}
        finally:
            if conn:
                conn.close()

        production = config.IS_PRODUCTION
        checks["session_secret"] = {
            "status": "ready" if not config.SECRET_KEY_IS_EPHEMERAL and len(config.SECRET_KEY) >= 32
                      else ("not_ready" if production else "warning")
        }
        checks["secure_session_cookie"] = {
            "status": "ready" if config.SESSION_HTTPS_ONLY else ("not_ready" if production else "warning")
        }
        backup_verified = os.getenv("SMART_BETHG_BACKUP_RESTORE_VERIFIED", "").strip().lower() == "true"
        checks["backup_restore_drill"] = {
            "status": "ready" if backup_verified else "not_ready",
            "detail": "Operator attestation is required after a successful restore drill.",
        }
        sandbox_enabled = os.getenv("SMART_BETHG_SANDBOX_ENABLED", "false").strip().lower() == "true"
        sandbox_image = os.getenv("SMART_BETHG_SANDBOX_PYTHON_IMAGE", "").strip()
        checks["sandbox"] = {
            "status": "ready" if (not sandbox_enabled or
                (sandbox_image in config.DOCKER_ALLOWED_IMAGES and "@sha256:" in sandbox_image))
                else "not_ready",
            "enabled": sandbox_enabled,
        }
        blocking = ["database", "migrations", "background_worker", "session_secret",
                    "secure_session_cookie", "backup_restore_drill", "sandbox"]
        ready = all(checks.get(key, {}).get("status") == "ready" for key in blocking)
        return {"status": "ready" if ready else "not_ready",
                "environment": config.ENVIRONMENT,
                "checked_at": datetime.now(timezone.utc).isoformat(),
                "checks": checks}
