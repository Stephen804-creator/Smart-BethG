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


def check_rate_limit(key: str, max_attempts=None, window_seconds=None) -> bool:
    """Record one attempt and return whether the key remains under its limit."""
    global _cleanup_counter
    key_hash = hashlib.sha256(str(key).encode("utf-8")).hexdigest()
    now = time.time()
    window = int(window_seconds or config.AUTH_RATE_LIMIT_WINDOW_SECONDS)
    limit = int(max_attempts or config.AUTH_RATE_LIMIT_MAX_ATTEMPTS)
    if limit < 1 or window < 1:
        raise ValueError("Rate-limit attempts and window must be positive.")
    cutoff = now - window
    database_url = (config.DATABASE_URL or "").strip()
    is_postgres = database_url.startswith(("postgres://", "postgresql://", "postgresql+psycopg://"))

    conn = get_connection()
    try:
        if is_postgres:
            # The UPSERT acquires a PostgreSQL row lock held until commit.
            # Unlike an in-process mutex, it serializes requests across replicas.
            conn.execute(
                "INSERT INTO auth_rate_limit_locks(key_hash, last_seen_epoch) VALUES (?, ?) "
                "ON CONFLICT(key_hash) DO UPDATE SET last_seen_epoch=excluded.last_seen_epoch",
                (key_hash, now),
            )
        else:
            # Serialize read-count-insert on the local SQLite database.
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                "INSERT INTO auth_rate_limit_locks(key_hash, last_seen_epoch) VALUES (?, ?) "
                "ON CONFLICT(key_hash) DO UPDATE SET last_seen_epoch=excluded.last_seen_epoch",
                (key_hash, now),
            )

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
            stale_before = now - max(window * 2, 600)
            conn.execute(
                "DELETE FROM auth_rate_limit_events WHERE hit_epoch < ?",
                (stale_before,),
            )
            conn.execute(
                "DELETE FROM auth_rate_limit_locks WHERE last_seen_epoch < ? "
                "AND NOT EXISTS (SELECT 1 FROM auth_rate_limit_events e "
                "WHERE e.key_hash=auth_rate_limit_locks.key_hash)",
                (stale_before,),
            )
        conn.commit()
        return allowed
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
