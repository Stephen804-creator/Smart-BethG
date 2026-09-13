"""
Smart BethG
Workspace Service

Provides safe, backend-derived information for the frontend.
"""

from __future__ import annotations

from typing import Any

from .ai_runtime import provider_status
from .codebase_service import inspect_project


def get_workspace_status() -> dict[str, Any]:
    """
    Return the current real application status.
    """

    provider = provider_status()

    try:
        project = inspect_project()

        codebase_status = {
            "available": True,
            "file_count": project[
                "file_count"
            ],
        }

    except Exception as exc:

        codebase_status = {
            "available": False,
            "error": str(exc),
        }

    return {
        "ok": True,
        "application": {
            "name": "Smart BethG",
            "version": "1.0.0",
            "status": "online",
        },
        "ai": provider,
        "developer": codebase_status,
        "capabilities": {
            "chat": provider["configured"],
            "web_search": True,
            "codebase_read": True,
            "codebase_write": False,
            "command_execution": False,
        },
    }
