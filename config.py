"""Central Smart BethG configuration.

LEARNING VERSION:
Keep environment-dependent values here so the rest of the application does
not scatter configuration and secrets throughout the codebase.
"""
from dataclasses import dataclass
import os

def _bool(value, default=False):
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}

@dataclass(frozen=True)
class Settings:
    app_name: str
    host: str
    port: int
    debug: bool
    secret_key: str
    default_model: str
    request_timeout_seconds: int
    max_task_steps: int

settings = Settings(
    app_name=os.getenv("SMART_BETHG_APP_NAME", "Smart BethG"),
    host=os.getenv("SMART_BETHG_HOST", "127.0.0.1"),
    port=int(os.getenv("SMART_BETHG_PORT", "8000")),
    debug=_bool(os.getenv("SMART_BETHG_DEBUG"), False),
    secret_key=os.getenv("SMART_BETHG_SECRET_KEY", "change-me"),
    default_model=os.getenv("SMART_BETHG_DEFAULT_MODEL", "local"),
    request_timeout_seconds=int(os.getenv("SMART_BETHG_REQUEST_TIMEOUT", "60")),
    max_task_steps=int(os.getenv("SMART_BETHG_MAX_TASK_STEPS", "20")),
)
