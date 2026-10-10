"""
Smart BethG - Logging

Centralised logging setup. Two destinations:

1. Console (stdout) - always configured. This is what Render's (or any
   host's) log viewer actually shows, which is how the last several bugs
   in this project were actually found and fixed - so it's the primary,
   non-negotiable destination.
2. Rotating files under config.STORAGE_DIRS["logs"] - best effort. If the
   storage root isn't writable (or isn't on a persistent disk), this
   silently degrades to console-only rather than crashing the app over
   a logging setup failure.

Named loggers (all children of "smart_bethg"):
- smart_bethg.app     general application lifecycle
- smart_bethg.auth    login/registration/session events
- smart_bethg.chat    chat requests, provider/model used, failures
- smart_bethg.task    task/tool execution
- smart_bethg.audit   security-relevant events (mirrors audit_events table)
- smart_bethg.error   unhandled exceptions (see error_handlers.py)
"""
import logging
import logging.handlers
import os
import sys

import config

_CONFIGURED = False


def setup_logging():
    global _CONFIGURED
    if _CONFIGURED:
        return
    _CONFIGURED = True

    root = logging.getLogger("smart_bethg")
    root.setLevel(logging.INFO)
    root.propagate = False

    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
    )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root.addHandler(console_handler)

    try:
        log_dir = config.STORAGE_DIRS["logs"]
        os.makedirs(log_dir, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            os.path.join(log_dir, "smart_bethg.log"),
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
        )
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)
    except OSError as exc:
        root.warning("File logging disabled (falling back to console-only): %s", exc)


def get_logger(name: str) -> logging.Logger:
    """name should be one of: app, auth, chat, task, audit, error."""
    setup_logging()
    return logging.getLogger(f"smart_bethg.{name}")
