import logging

from database import get_connection
from providers.provider_manager import provider_manager

logger = logging.getLogger("smart_bethg.health")


def check_database():
    try:
        conn = get_connection()
        try:
            conn.execute("SELECT 1")
        finally:
            conn.close()
        return {"status": "ok"}
    except Exception:
        # Keep connection strings, paths, and driver errors out of a public
        # health response. The full exception remains in server logs only.
        logger.exception("Database health check failed")
        return {"status": "error", "detail": "Database connection is unavailable."}


def check_providers():
    available = provider_manager.available_providers()
    return {
        "status": "ok" if available else "not_configured",
        "available": available,
        "default": provider_manager.default_provider_name(),
    }


def check_background_worker():
    """Check persisted worker heartbeats; never infer liveness from configuration alone."""
    try:
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT COUNT(*) AS count FROM worker_heartbeats "
                "WHERE status='healthy' AND last_seen >= CURRENT_TIMESTAMP - INTERVAL '90 seconds'"
            ).fetchone()
            count = int(row["count"])
        finally:
            conn.close()
        return {
            "status": "ok" if count else "not_running",
            "healthy_workers": count,
        }
    except Exception:
        logger.exception("Background worker health check failed")
        return {"status": "unknown", "healthy_workers": 0}
