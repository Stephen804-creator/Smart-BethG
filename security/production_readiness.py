"""Production security checks used by startup and readiness endpoints."""
from urllib.parse import urlsplit

import config


def security_readiness():
    checks = {
        "stable_session_secret": not config.SECRET_KEY_IS_EPHEMERAL and len(config.SECRET_KEY) >= 32,
        "https_only_session_cookie": (not config.IS_PRODUCTION) or config.SESSION_HTTPS_ONLY,
        "database_configured": bool(config.DATABASE_URL and config.DATABASE_URL.startswith(
            ("postgres://", "postgresql://", "postgresql+psycopg://")
        )),
        "production_origins_use_https": True,
        "sandbox_configuration_valid": True,
    }
    if config.IS_PRODUCTION:
        checks["production_origins_use_https"] = all(
            urlsplit(origin).scheme == "https" and bool(urlsplit(origin).netloc)
            for origin in config.ALLOWED_ORIGINS
        )
    if getattr(config, "SANDBOX_ENABLED", False):
        image = getattr(config, "SANDBOX_PYTHON_IMAGE", "")
        checks["sandbox_configuration_valid"] = bool(
            image and image in config.DOCKER_ALLOWED_IMAGES
        )
    return {
        "status": "ok" if all(checks.values()) else "degraded",
        "checks": checks,
    }


def validate_startup_security():
    """Fail closed on unsafe production settings instead of silently weakening security."""
    report = security_readiness()
    if config.IS_PRODUCTION and report["status"] != "ok":
        failed = [name for name, passed in report["checks"].items() if not passed]
        raise RuntimeError("Production security configuration failed: " + ", ".join(failed))
    return report
