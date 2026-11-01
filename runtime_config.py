"""Runtime configuration for the monolith-first execution model.

The application is kept in one deployable codebase for now, but it still supports
explicit runtime roles so the web/API process and the background worker process can
be separated cleanly later without a full distributed rewrite.
"""
import os

RUNTIME_ROLE = os.getenv("SMART_BETHG_RUNTIME", "api").strip().lower()
if RUNTIME_ROLE not in {"api", "worker"}:
    raise RuntimeError("SMART_BETHG_RUNTIME must be one of: api, worker")

RUNTIME_ROLES = {"api", "worker"}
