"""Queue dispatch for expensive jobs in the monolith-first runtime model.

The application remains a single deployable app, but the runtime boundaries are
made explicit: the API layer enqueues long-running work while the worker runtime
claims and executes it from the durable queue.
"""

from __future__ import annotations

from services.job_queue import JobQueue

_queue = JobQueue()


def enqueue_job(user_id, job_type, payload, idempotency_key, priority=0, max_attempts=5):
    """Enqueue a durable background job for worker execution."""
    return _queue.enqueue(
        user_id=user_id,
        job_type=job_type,
        payload=payload,
        idempotency_key=idempotency_key,
        priority=priority,
        max_attempts=max_attempts,
    )
