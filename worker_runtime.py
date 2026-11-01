"""Deprecated compatibility shim for the worker boundary.

The app is intentionally structured as a modular monolith for now, but the
background execution runtime is isolated by this module so it can later be
promoted to a dedicated worker service without changing domain logic.
"""

from __future__ import annotations

from workers.handlers import default_job_handlers
from workers.runner import run_worker_loop

__all__ = ["default_job_handlers", "run_worker_loop"]
