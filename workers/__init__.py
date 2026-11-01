"""Worker boundary for long-running jobs.

This package intentionally separates the web/API runtime from background execution.
The application can still run as a modular monolith, but worker responsibilities are
isolated here so they can later be moved to a dedicated process or service without
rewriting the domain logic.
"""

from .handlers import default_job_handlers
from .runner import run_worker_loop

__all__ = ["default_job_handlers", "run_worker_loop"]
