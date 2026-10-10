from database import get_connection
from providers.provider_manager import provider_manager


def check_database():
    try:
        conn = get_connection()
        try:
            conn.execute("SELECT 1")
        finally:
            conn.close()
        return {"status": "ok"}
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}


def check_providers():
    available = provider_manager.available_providers()
    return {
        "status": "ok" if available else "not_configured",
        "available": available,
        "default": provider_manager.default_provider_name(),
    }


def check_background_worker():
    """
    There is no background worker/task-execution process yet (see
    v1_capabilities.md - task execution is still queue-only), so this is
    honestly reported as not implemented rather than omitted or faked as
    healthy.
    """
    return {
        "status": "not_implemented",
        "detail": "Tasks are queued (POST /tasks) but nothing executes them yet.",
    }
