"""
Smart BethG - Configuration

Centralises environment-driven configuration so no module hardcodes a
deployment location, secret, or storage path. Every setting here has a
safe local-development default and can be overridden by an environment
variable in any deployment target (Render, another host, or local).
"""
import os
import secrets
import warnings

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------
ENVIRONMENT = os.getenv("SMART_BETHG_ENV", "development")
IS_PRODUCTION = ENVIRONMENT.lower() == "production"

# ---------------------------------------------------------------------------
# Storage root (all persistent files/directories live under here)
# ---------------------------------------------------------------------------
STORAGE_ROOT = os.getenv("SMART_BETHG_STORAGE_ROOT", "./storage")

STORAGE_DIRS = {
    "uploads": os.path.join(STORAGE_ROOT, "uploads"),
    "memory": os.path.join(STORAGE_ROOT, "memory"),
    "research": os.path.join(STORAGE_ROOT, "research"),
    "projects": os.path.join(STORAGE_ROOT, "projects"),
    "social": os.path.join(STORAGE_ROOT, "social"),
    "missions": os.path.join(STORAGE_ROOT, "missions"),
    "artifacts": os.path.join(STORAGE_ROOT, "artifacts"),
    "workflows": os.path.join(STORAGE_ROOT, "workflows"),
    "logs": os.path.join(STORAGE_ROOT, "logs"),
    "db": os.path.join(STORAGE_ROOT, "db"),
}


def ensure_storage_dirs():
    """Create every V1 storage directory if it does not already exist."""
    for path in STORAGE_DIRS.values():
        os.makedirs(path, exist_ok=True)


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
# DATABASE_URL is retained as a configuration boundary for a future
# database-engine migration. Only sqlite:/// and plain file paths are
# currently supported; anything else fails fast rather than being passed
# to sqlite3.connect() silently.
DATABASE_URL = os.getenv("DATABASE_URL", "")


def resolve_sqlite_path() -> str:
    """Resolve the on-disk SQLite path from DATABASE_URL / legacy env var."""
    if DATABASE_URL:
        if DATABASE_URL.startswith("sqlite:///"):
            return DATABASE_URL.replace("sqlite:///", "", 1)
        raise ValueError(
            f"Unsupported DATABASE_URL scheme for V1 (SQLite only): {DATABASE_URL!r}"
        )
    legacy = os.getenv("SMART_BETHG_DB")
    if legacy:
        return legacy
    return os.path.join(STORAGE_DIRS["db"], "smart_bethg.db")


# ---------------------------------------------------------------------------
# Sessions / security
# ---------------------------------------------------------------------------
_SECRET_KEY = os.getenv("SMART_BETHG_SECRET_KEY", "")
if not _SECRET_KEY:
    if IS_PRODUCTION:
        raise RuntimeError(
            "SMART_BETHG_SECRET_KEY must be set when SMART_BETHG_ENV=production."
        )
    warnings.warn(
        "SMART_BETHG_SECRET_KEY is not set; using a temporary random key for "
        "this process only. Sessions will not survive a restart. Set "
        "SMART_BETHG_SECRET_KEY before deploying.",
        RuntimeWarning,
    )
    _SECRET_KEY = secrets.token_hex(32)
SECRET_KEY = _SECRET_KEY

SESSION_COOKIE_NAME = os.getenv("SMART_BETHG_SESSION_COOKIE", "smart_bethg_session")
SESSION_HTTPS_ONLY = os.getenv("SMART_BETHG_SESSION_HTTPS_ONLY", "true" if IS_PRODUCTION else "false").lower() == "true"

# ---------------------------------------------------------------------------
# AI providers (no key hardcoded; capability is honestly absent without one)
# ---------------------------------------------------------------------------
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-3-5-haiku-20241022")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# GOOGLE_API_KEY is the primary name; GEMINI_API_KEY is accepted as an
# alias since Google's own docs use both names interchangeably.
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", os.getenv("GEMINI_API_KEY", ""))
GOOGLE_MODEL = os.getenv("GOOGLE_MODEL", "gemini-2.0-flash")

# Which provider chat uses when the user/request doesn't specify one.
# If unset or not actually configured, falls back to priority order:
# anthropic > openai > google.
DEFAULT_PROVIDER = os.getenv("SMART_BETHG_DEFAULT_PROVIDER", "")

# ---------------------------------------------------------------------------
# CORS (only relevant if a separate frontend origin is ever introduced)
# ---------------------------------------------------------------------------
ALLOWED_ORIGINS = [o.strip() for o in os.getenv("SMART_BETHG_ALLOWED_ORIGINS", "").split(",") if o.strip()]

# ---------------------------------------------------------------------------
# Registration / abuse controls
# ---------------------------------------------------------------------------
# Open by default so a single operator can create their own account while
# testing pre-domain. Set to "false" before a public launch, or set
# REGISTRATION_INVITE_CODE to require a shared code at signup.
REGISTRATION_OPEN = os.getenv("SMART_BETHG_REGISTRATION_OPEN", "true").lower() == "true"
REGISTRATION_INVITE_CODE = os.getenv("SMART_BETHG_INVITE_CODE", "")

# Simple in-memory rate limits (per process, per IP). Fine for a single
# instance; will not coordinate across multiple instances/replicas -
# use a shared store (e.g. Redis) instead if you scale beyond one.
AUTH_RATE_LIMIT_MAX_ATTEMPTS = int(os.getenv("SMART_BETHG_AUTH_RATE_LIMIT_MAX", "10"))
AUTH_RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("SMART_BETHG_AUTH_RATE_LIMIT_WINDOW", "300"))
