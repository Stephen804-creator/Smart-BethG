"""
Smart BethG
Codebase Service

Provides safe read-only inspection of a project directory.

This is the first foundation for the Developer workspace.

It can:

- inspect project structure
- list files
- read text files
- search text across a codebase
- produce a compact project summary

It does NOT modify files yet.

File modification, command execution, testing and verification
will be added only after the read-only foundation is working.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any


IGNORED_DIRECTORIES = {
    ".git",
    ".hg",
    ".svn",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "node_modules",
    ".venv",
    "venv",
    "env",
    ".env",
    "dist",
    "build",
    ".next",
    ".nuxt",
    "coverage",
}


TEXT_EXTENSIONS = {
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".html",
    ".css",
    ".scss",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".ini",
    ".cfg",
    ".md",
    ".txt",
    ".xml",
    ".sql",
    ".sh",
    ".bash",
    ".ps1",
    ".java",
    ".kt",
    ".c",
    ".h",
    ".cpp",
    ".hpp",
    ".rs",
    ".go",
    ".php",
    ".rb",
}


MAX_FILE_SIZE = 1_000_000
MAX_READ_CHARS = 60_000


class CodebaseServiceError(Exception):
    """Raised when codebase inspection fails."""


def get_project_root() -> Path:
    """
    Return the Smart BethG project root.
    """

    return Path(
        __file__
    ).resolve().parent.parent


def _is_ignored(path: Path) -> bool:
    """
    Determine whether a path should be ignored.
    """

    return any(
        part in IGNORED_DIRECTORIES
        for part in path.parts
    )


def _safe_path(
    relative_path: str,
) -> Path:
    """
    Resolve a user-supplied relative path safely.

    The path cannot escape the Smart BethG project root.
    """

    root = get_project_root()

    relative = Path(
        relative_path.strip()
    )

    if relative.is_absolute():
        raise CodebaseServiceError(
            "Absolute paths are not allowed."
        )

    candidate = (
        root / relative
    ).resolve()

    try:
        candidate.relative_to(root)
    except ValueError as exc:

        raise CodebaseServiceError(
            "The requested path is outside "
            "the Smart BethG project."
        ) from exc

    return candidate


def _iter_files(
    root: Path,
):
    """
    Iterate through inspectable project files.
    """

    if not root.exists():
        return

    for current_root, directories, files in os.walk(root):

        current_path = Path(
            current_root
        )

        directories[:] = [
            directory
            for directory in directories
            if directory not in IGNORED_DIRECTORIES
        ]

        if _is_ignored(current_path):
            continue

        for filename in files:

            path = (
                current_path / filename
            )

            if _is_ignored(path):
                continue

            try:

                if path.stat().st_size > MAX_FILE_SIZE:
                    continue

            except OSError:
                continue

            yield path


def list_files(
    relative_path: str = ".",
    limit: int = 500,
) -> dict[str, Any]:
    """
    List files inside the requested project directory.
    """

    root = _safe_path(
        relative_path
    )

    if not root.exists():
        raise CodebaseServiceError(
            "The requested directory does not exist."
        )

    if not root.is_dir():
        raise CodebaseServiceError(
            "The requested path is not a directory."
        )

    files: list[str] = []

    for path in _iter_files(root):

        if len(files) >= limit:
            break

        files.append(
            str(
                path.relative_to(
                    get_project_root()
                )
            ).replace(
                os.sep,
                "/",
            )
        )

    files.sort()

    return {
        "ok": True,
        "root": relative_path,
        "count": len(files),
        "files": files,
    }


def read_file(
    relative_path: str,
) -> dict[str, Any]:
    """
    Read one text file from the project.
    """

    path = _safe_path(
        relative_path
    )

    if not path.exists():
        raise CodebaseServiceError(
            "The requested file does not exist."
        )

    if not path.is_file():
        raise CodebaseServiceError(
            "The requested path is not a file."
        )

    if path.stat().st_size > MAX_FILE_SIZE:
        raise CodebaseServiceError(
            "The requested file is too large to inspect."
        )

    if (
        path.suffix.lower()
        not in TEXT_EXTENSIONS
    ):
        raise CodebaseServiceError(
            "This file type is not currently "
            "supported for text inspection."
        )

    try:

        content = path.read_text(
            encoding="utf-8",
            errors="replace",
        )

    except OSError as exc:

        raise CodebaseServiceError(
            f"Unable to read file: {exc}"
        ) from exc

    truncated = False

    if len(content) > MAX_READ_CHARS:

        content = (
            content[:MAX_READ_CHARS]
        )

        truncated = True

    return {
        "ok": True,
        "path": str(
            path.relative_to(
                get_project_root()
            )
        ).replace(
            os.sep,
            "/",
        ),
        "content": content,
        "truncated": truncated,
    }


def search_code(
    query: str,
    relative_path: str = ".",
    limit: int = 100,
) -> dict[str, Any]:
    """
    Search for text inside the project codebase.
    """

    query = query.strip()

    if not query:
        raise ValueError(
            "Code search query cannot be empty."
        )

    root = _safe_path(
        relative_path
    )

    if not root.exists():
        raise CodebaseServiceError(
            "The requested directory does not exist."
        )

    results: list[dict[str, Any]] = []

    query_lower = query.lower()

    for path in _iter_files(root):

        if len(results) >= limit:
            break

        if (
            path.suffix.lower()
            not in TEXT_EXTENSIONS
        ):
            continue

        try:

            content = path.read_text(
                encoding="utf-8",
                errors="replace",
            )

        except OSError:
            continue

        for line_number, line in enumerate(
            content.splitlines(),
            start=1,
        ):

            if query_lower not in line.lower():
                continue

            results.append(
                {
                    "path": str(
                        path.relative_to(
                            get_project_root()
                        )
                    ).replace(
                        os.sep,
                        "/",
                    ),
                    "line": line_number,
                    "text": line.strip()[:500],
                }
            )

            if len(results) >= limit:
                break

    return {
        "ok": True,
        "query": query,
        "count": len(results),
        "results": results,
    }


def inspect_project() -> dict[str, Any]:
    """
    Produce a compact structural summary of the project.
    """

    root = get_project_root()

    file_list = list_files(
        ".",
        limit=1000,
    )

    extensions: dict[str, int] = {}

    for relative in file_list["files"]:

        suffix = Path(
            relative
        ).suffix.lower()

        if not suffix:
            suffix = "[no extension]"

        extensions[suffix] = (
            extensions.get(suffix, 0) + 1
        )

    return {
        "ok": True,
        "project_root": str(root),
        "file_count": file_list["count"],
        "extensions": dict(
            sorted(
                extensions.items(),
                key=lambda item: (
                    -item[1],
                    item[0],
                ),
            )
        ),
        "sample_files": file_list[
            "files"
        ][:100],
    }
