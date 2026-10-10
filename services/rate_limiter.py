"""
Shared, database-backed authentication rate limiter.

PostgreSQL is the production backend, so all application replicas share the
same counters. PostgreSQL transaction-scoped advisory locks serialize updates
for one hashed key; SQLite uses BEGIN IMMEDIATE for local development/tests.
No client IP or raw limiter key is persisted, only a SHA-256 digest.
"""
import hashlib
import time

import config
from database import get_connection

_cleanup_counter = 0


def check_rate_limit(key: str) -> bool:
    """Record one attempt and return whether the key remains under its limit."""
    global _cleanup_counter
    key_hash = hashlib.sha256(str(key).encode("utf-8")).hexdigest()
    now = time.time()
    cutoff = now - config.AUTH_RATE_LIMIT_WINDOW_SECONDS
    limit = config.AUTH_RATE_LIMIT_MAX_ATTEMPTS
    database_url = (config.DATABASE_URL or "").strip()
    is_postgres = database_url.startswith(("postgres://", "postgresql://", "postgresql+psycopg://"))

    conn = get_connection()
    try:
        if is_postgres:
            # The lock is held until commit/rollback and coordinates replicas.
            conn.execute("SELECT pg_advisory_xact_lock(hashtext(?))", (key_hash,))
        else:
            # Serialize read-count-insert on the local SQLite database.
            conn.execute("BEGIN IMMEDIATE")

        conn.execute(
            "DELETE FROM auth_rate_limit_events WHERE key_hash=? AND hit_epoch < ?",
            (key_hash, cutoff),
        )
        row = conn.execute(
            "SELECT COUNT(*) AS hits FROM auth_rate_limit_events WHERE key_hash=? AND hit_epoch >= ?",
            (key_hash, cutoff),
        ).fetchone()
        allowed = int(row["hits"] or 0) < limit
        if allowed:
            conn.execute(
                "INSERT INTO auth_rate_limit_events(key_hash, hit_epoch) VALUES (?, ?)",
                (key_hash, now),
            )

        _cleanup_counter += 1
        if _cleanup_counter % 100 == 0:
            conn.execute(
                "DELETE FROM auth_rate_limit_events WHERE hit_epoch < ?",
                (now - max(config.AUTH_RATE_LIMIT_WINDOW_SECONDS * 2, 600),),
            )
        conn.commit()
        return allowed
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
