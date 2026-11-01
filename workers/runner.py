"""Worker runner entry point.

This keeps the web app and background execution responsibilities separated while
preserving the current codebase layout.
"""

from __future__ import annotations

import time
from typing import Callable, Dict, Optional

from logging_setup import get_logger
from services.job_queue import JobWorker

from .handlers import default_job_handlers

logger = get_logger("worker")


def run_worker_loop(
    poll_interval: float = 1.0,
    handlers: Optional[Dict[str, Callable]] = None,
    stop_after: Optional[int] = None,
) -> None:
    """Run the durable worker loop.

    Args:
        poll_interval: seconds between queue polls.
        handlers: optional map of job_type -> callback. Defaults to the trusted
            registry in workers.handlers.
        stop_after: optional number of successful queue polls before exiting.
    """
    worker = JobWorker(handlers=handlers or default_job_handlers())
    iterations = 0

    while True:
        if stop_after is not None and iterations >= stop_after:
            return
        try:
            worked = worker.run_once()
        except Exception:
            logger.exception("Worker poll failed")
            worked = False
        if worked:
            iterations += 1
        else:
            time.sleep(poll_interval)
