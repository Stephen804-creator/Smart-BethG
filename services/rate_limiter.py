"""
Minimal in-memory rate limiter.

Scope and honest limitations:
- Per-process only. If you run more than one instance/replica behind a
  load balancer, each instance tracks its own counters independently -
  this will NOT correctly rate-limit an attacker spread across
  instances. Replace with a shared store (e.g. Redis) before scaling
  horizontally.
- Counters are never evicted proactively; a background sweep trims old
  entries on each call so memory stays bounded for realistic traffic,
  but this is not built for high request volume.
"""
import time
import threading

import config

_lock = threading.Lock()
_hits: dict[str, list[float]] = {}


def check_rate_limit(key: str) -> bool:
    """
    Record a hit for `key` (e.g. "login:203.0.113.4") and return True if
    the caller is still within the allowed rate, False if they have
    exceeded it and should be rejected.
    """
    now = time.monotonic()
    window = config.AUTH_RATE_LIMIT_WINDOW_SECONDS
    limit = config.AUTH_RATE_LIMIT_MAX_ATTEMPTS

    with _lock:
        timestamps = _hits.setdefault(key, [])
        cutoff = now - window
        while timestamps and timestamps[0] < cutoff:
            timestamps.pop(0)

        if len(timestamps) >= limit:
            return False

        timestamps.append(now)
        return True
