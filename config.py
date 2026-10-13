"""
Smart BethG - Configuration

Centralises environment-driven configuration so no module hardcodes a
deployment location, secret, or storage path. Settings are environment-driven
so the same application package can run locally or on any compatible host.
"""
import os
import secrets
import warnings

ENVIRONMENT = os.getenv("SMART_BETHG_ENV", "development").strip().lower()
if ENVIRONMENT not in {"development", "test", "production"}:
    raise RuntimeError(
        "SMART_BETHG_ENV must be one of: development, test, production. "
        "Refusing to silently treat an unknown environment as development."
    )
IS_PRODUCTION = ENVIRONMENT == "production"
API_PREFIX = "/api/v1"

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


# PostgreSQL is the only application database in every environment.
# Set DATABASE_URL to a local PostgreSQL instance for development and tests.
# Legacy SQLite files are read only by the explicit migration utility.
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()


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
SESSION_HTTPS_ONLY = os.getenv(
    "SMART_BETHG_SESSION_HTTPS_ONLY", "true" if IS_PRODUCTION else "false"
).lower() == "true"

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", os.getenv("GEMINI_API_KEY", ""))
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
DEFAULT_PROVIDER = os.getenv("SMART_BETHG_DEFAULT_PROVIDER", "")

GOOGLE_OAUTH_CLIENT_ID = os.getenv("GOOGLE_OAUTH_CLIENT_ID", "")
GOOGLE_OAUTH_CLIENT_SECRET = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", "")
GOOGLE_OAUTH_ENABLED = bool(GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET)

# Comma-separated exact origins. Empty means no cross-origin browser access.
ALLOWED_ORIGINS = [
    origin.strip().rstrip("/")
    for origin in os.getenv("SMART_BETHG_ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
]

# Development stays convenient, but production registration is closed unless
# the operator explicitly opts in. Existing users can still log in.
REGISTRATION_OPEN = os.getenv("SMART_BETHG_REGISTRATION_OPEN", "false").lower() == "true"
REGISTRATION_INVITE_CODE = os.getenv("SMART_BETHG_INVITE_CODE", "")

# Database-backed rate limiting uses these limits across processes and replicas.
AUTH_RATE_LIMIT_MAX_ATTEMPTS = int(os.getenv("SMART_BETHG_AUTH_RATE_LIMIT_MAX", "10"))
AUTH_RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("SMART_BETHG_AUTH_RATE_LIMIT_WINDOW", "300"))

MAX_UPLOAD_SIZE_BYTES = int(
    os.getenv("SMART_BETHG_MAX_UPLOAD_BYTES", str(15 * 1024 * 1024))
)
BRAVE_SEARCH_API_KEY = os.getenv("BRAVE_SEARCH_API_KEY", "")

# Docker execution is opt-in and restricted to exact, operator-approved image tags.
DOCKER_ALLOWED_IMAGES = {
    image.strip() for image in os.getenv("SMART_BETHG_DOCKER_ALLOWED_IMAGES", "").split(",")
    if image.strip()
}

# Host Python execution is for local development only. Production requires a real isolated job runner.
ALLOW_DEV_PYTHON_EXECUTION = (
    not IS_PRODUCTION
    and os.getenv("SMART_BETHG_ALLOW_DEV_PYTHON_EXECUTION", "true").lower() == "true"
)

CHAT_RATE_LIMIT_MAX_ATTEMPTS = int(os.getenv("SMART_BETHG_CHAT_RATE_LIMIT_MAX", "30"))
CHAT_RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("SMART_BETHG_CHAT_RATE_LIMIT_WINDOW", "60"))
UPLOAD_RATE_LIMIT_MAX_ATTEMPTS = int(os.getenv("SMART_BETHG_UPLOAD_RATE_LIMIT_MAX", "20"))
UPLOAD_RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("SMART_BETHG_UPLOAD_RATE_LIMIT_WINDOW", "3600"))
TASK_RATE_LIMIT_MAX_ATTEMPTS = int(os.getenv("SMART_BETHG_TASK_RATE_LIMIT_MAX", "20"))
TASK_RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("SMART_BETHG_TASK_RATE_LIMIT_WINDOW", "300"))
MAX_CHAT_MESSAGE_CHARS = int(os.getenv("SMART_BETHG_MAX_CHAT_MESSAGE_CHARS", "20000"))
MAX_PROVIDER_ATTEMPTS_PER_CHAT = int(os.getenv("SMART_BETHG_MAX_PROVIDER_ATTEMPTS_PER_CHAT", "3"))

MAX_CHAT_CONTEXT_CHARS = int(os.getenv("SMART_BETHG_MAX_CHAT_CONTEXT_CHARS", "60000"))
CHAT_MAX_OUTPUT_TOKENS = int(os.getenv("SMART_BETHG_CHAT_MAX_OUTPUT_TOKENS", "2048"))

# Conservative daily budgets. Dollar amounts are estimates based on the
# dated model-catalog rates; also configure provider-side spend limits.
USER_DAILY_TOKEN_BUDGET = int(os.getenv("SMART_BETHG_USER_DAILY_TOKEN_BUDGET", "100000"))
GLOBAL_DAILY_TOKEN_BUDGET = int(os.getenv("SMART_BETHG_GLOBAL_DAILY_TOKEN_BUDGET", "1000000"))
USER_DAILY_SPEND_USD = float(os.getenv("SMART_BETHG_USER_DAILY_SPEND_USD", "2.0"))
GLOBAL_DAILY_SPEND_USD = float(os.getenv("SMART_BETHG_GLOBAL_DAILY_SPEND_USD", "25.0"))
USER_DAILY_REQUEST_BUDGET = int(os.getenv("SMART_BETHG_USER_DAILY_REQUEST_BUDGET", "100"))
GLOBAL_DAILY_REQUEST_BUDGET = int(os.getenv("SMART_BETHG_GLOBAL_DAILY_REQUEST_BUDGET", "2000"))
UNKNOWN_MODEL_INPUT_USD_PER_MILLION = float(os.getenv("SMART_BETHG_UNKNOWN_MODEL_INPUT_USD_PER_MILLION", "20.0"))
UNKNOWN_MODEL_OUTPUT_USD_PER_MILLION = float(os.getenv("SMART_BETHG_UNKNOWN_MODEL_OUTPUT_USD_PER_MILLION", "100.0"))

SESSION_MAX_AGE_SECONDS = int(os.getenv("SMART_BETHG_SESSION_MAX_AGE_SECONDS", "43200"))

KNOWLEDGE_SEARCH_RATE_LIMIT_MAX_ATTEMPTS = int(os.getenv("SMART_BETHG_KNOWLEDGE_SEARCH_RATE_LIMIT_MAX", "20"))
KNOWLEDGE_SEARCH_RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("SMART_BETHG_KNOWLEDGE_SEARCH_RATE_LIMIT_WINDOW", "60"))

MAX_EXTRACTED_TEXT_CHARS = int(os.getenv("SMART_BETHG_MAX_EXTRACTED_TEXT_CHARS", "1000000"))
MAX_FILE_SEARCH_CHARS = int(os.getenv("SMART_BETHG_MAX_FILE_SEARCH_CHARS", "1000000"))
MAX_PDF_PAGES = int(os.getenv("SMART_BETHG_MAX_PDF_PAGES", "500"))
FILE_SEARCH_RATE_LIMIT_MAX_ATTEMPTS = int(os.getenv("SMART_BETHG_FILE_SEARCH_RATE_LIMIT_MAX", "60"))
FILE_SEARCH_RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("SMART_BETHG_FILE_SEARCH_RATE_LIMIT_WINDOW", "60"))
FILE_EXTRACT_RATE_LIMIT_MAX_ATTEMPTS = int(os.getenv("SMART_BETHG_FILE_EXTRACT_RATE_LIMIT_MAX", "30"))
FILE_EXTRACT_RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("SMART_BETHG_FILE_EXTRACT_RATE_LIMIT_WINDOW", "300"))
FILE_INGEST_RATE_LIMIT_MAX_ATTEMPTS = int(os.getenv("SMART_BETHG_FILE_INGEST_RATE_LIMIT_MAX", "10"))
FILE_INGEST_RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("SMART_BETHG_FILE_INGEST_RATE_LIMIT_WINDOW", "300"))

MAX_KNOWLEDGE_CHARS_PER_FILE = int(os.getenv("SMART_BETHG_MAX_KNOWLEDGE_CHARS_PER_FILE", "160000"))
MAX_KNOWLEDGE_CHUNKS_PER_FILE = int(os.getenv("SMART_BETHG_MAX_KNOWLEDGE_CHUNKS_PER_FILE", "200"))
EMBEDDING_BATCH_SIZE = int(os.getenv("SMART_BETHG_EMBEDDING_BATCH_SIZE", "16"))


def _validate_runtime_config() -> None:
    """Fail fast when resource limits or production security settings are unsafe."""
    positive_integer_settings = {
        "AUTH_RATE_LIMIT_MAX_ATTEMPTS": AUTH_RATE_LIMIT_MAX_ATTEMPTS,
        "AUTH_RATE_LIMIT_WINDOW_SECONDS": AUTH_RATE_LIMIT_WINDOW_SECONDS,
        "MAX_UPLOAD_SIZE_BYTES": MAX_UPLOAD_SIZE_BYTES,
        "CHAT_RATE_LIMIT_MAX_ATTEMPTS": CHAT_RATE_LIMIT_MAX_ATTEMPTS,
        "CHAT_RATE_LIMIT_WINDOW_SECONDS": CHAT_RATE_LIMIT_WINDOW_SECONDS,
        "UPLOAD_RATE_LIMIT_MAX_ATTEMPTS": UPLOAD_RATE_LIMIT_MAX_ATTEMPTS,
        "UPLOAD_RATE_LIMIT_WINDOW_SECONDS": UPLOAD_RATE_LIMIT_WINDOW_SECONDS,
        "TASK_RATE_LIMIT_MAX_ATTEMPTS": TASK_RATE_LIMIT_MAX_ATTEMPTS,
        "TASK_RATE_LIMIT_WINDOW_SECONDS": TASK_RATE_LIMIT_WINDOW_SECONDS,
        "MAX_CHAT_MESSAGE_CHARS": MAX_CHAT_MESSAGE_CHARS,
        "MAX_PROVIDER_ATTEMPTS_PER_CHAT": MAX_PROVIDER_ATTEMPTS_PER_CHAT,
        "MAX_CHAT_CONTEXT_CHARS": MAX_CHAT_CONTEXT_CHARS,
        "CHAT_MAX_OUTPUT_TOKENS": CHAT_MAX_OUTPUT_TOKENS,
        "USER_DAILY_TOKEN_BUDGET": USER_DAILY_TOKEN_BUDGET,
        "GLOBAL_DAILY_TOKEN_BUDGET": GLOBAL_DAILY_TOKEN_BUDGET,
        "USER_DAILY_REQUEST_BUDGET": USER_DAILY_REQUEST_BUDGET,
        "GLOBAL_DAILY_REQUEST_BUDGET": GLOBAL_DAILY_REQUEST_BUDGET,
        "SESSION_MAX_AGE_SECONDS": SESSION_MAX_AGE_SECONDS,
        "KNOWLEDGE_SEARCH_RATE_LIMIT_MAX_ATTEMPTS": KNOWLEDGE_SEARCH_RATE_LIMIT_MAX_ATTEMPTS,
        "KNOWLEDGE_SEARCH_RATE_LIMIT_WINDOW_SECONDS": KNOWLEDGE_SEARCH_RATE_LIMIT_WINDOW_SECONDS,
        "MAX_EXTRACTED_TEXT_CHARS": MAX_EXTRACTED_TEXT_CHARS,
        "MAX_FILE_SEARCH_CHARS": MAX_FILE_SEARCH_CHARS,
        "MAX_PDF_PAGES": MAX_PDF_PAGES,
        "FILE_SEARCH_RATE_LIMIT_MAX_ATTEMPTS": FILE_SEARCH_RATE_LIMIT_MAX_ATTEMPTS,
        "FILE_SEARCH_RATE_LIMIT_WINDOW_SECONDS": FILE_SEARCH_RATE_LIMIT_WINDOW_SECONDS,
        "FILE_EXTRACT_RATE_LIMIT_MAX_ATTEMPTS": FILE_EXTRACT_RATE_LIMIT_MAX_ATTEMPTS,
        "FILE_EXTRACT_RATE_LIMIT_WINDOW_SECONDS": FILE_EXTRACT_RATE_LIMIT_WINDOW_SECONDS,
        "FILE_INGEST_RATE_LIMIT_MAX_ATTEMPTS": FILE_INGEST_RATE_LIMIT_MAX_ATTEMPTS,
        "FILE_INGEST_RATE_LIMIT_WINDOW_SECONDS": FILE_INGEST_RATE_LIMIT_WINDOW_SECONDS,
        "MAX_KNOWLEDGE_CHARS_PER_FILE": MAX_KNOWLEDGE_CHARS_PER_FILE,
        "MAX_KNOWLEDGE_CHUNKS_PER_FILE": MAX_KNOWLEDGE_CHUNKS_PER_FILE,
        "EMBEDDING_BATCH_SIZE": EMBEDDING_BATCH_SIZE,
    }
    invalid = [
        f"{name} must be greater than zero"
        for name, value in positive_integer_settings.items()
        if value <= 0
    ]
    positive_money_settings = {
        "USER_DAILY_SPEND_USD": USER_DAILY_SPEND_USD,
        "GLOBAL_DAILY_SPEND_USD": GLOBAL_DAILY_SPEND_USD,
        "UNKNOWN_MODEL_INPUT_USD_PER_MILLION": UNKNOWN_MODEL_INPUT_USD_PER_MILLION,
        "UNKNOWN_MODEL_OUTPUT_USD_PER_MILLION": UNKNOWN_MODEL_OUTPUT_USD_PER_MILLION,
    }
    import math

    invalid.extend(
        f"{name} must be a finite number greater than zero"
        for name, value in positive_money_settings.items()
        if not math.isfinite(value) or value <= 0
    )
    if invalid:
        raise RuntimeError("Invalid Smart BethG configuration: " + "; ".join(invalid) + ".")

    if IS_PRODUCTION:
        database_url = DATABASE_URL.strip().lower()
        if not database_url.startswith(("postgres://", "postgresql://", "postgresql+psycopg://")):
            raise RuntimeError(
                "Production requires DATABASE_URL pointing to PostgreSQL; "
                "SQLite is supported only as a read-only migration source."
            )
        if not SESSION_HTTPS_ONLY:
            raise RuntimeError(
                "SMART_BETHG_SESSION_HTTPS_ONLY must be true in production "
                "so session cookies are not sent over plain HTTP."
            )


_validate_runtime_config()
