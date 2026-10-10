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
    """Report the current synchronous request model honestly."""
    return {
        "status": "not_implemented",
        "detail": (
            "The current /tasks endpoint executes synchronously within the request. "
            "A durable worker for missions and workflows is not implemented yet."
        ),
    }
