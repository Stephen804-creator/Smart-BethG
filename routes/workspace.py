"""
Smart BethG
Workspace API Routes
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from services.ai_runtime import (
    AIRuntimeError,
    AIProviderNotConfigured,
    generate_response,
    provider_status,
)

from services.codebase_service import (
    CodebaseServiceError,
    inspect_project,
    list_files,
    read_file,
    search_code,
)

from services.search_service import (
    SearchServiceError,
    search_web,
)

from services.workspace_service import (
    get_workspace_status,
)


router = APIRouter(
    prefix="/api/workspace",
    tags=["workspace"],
)


class ChatRequest(BaseModel):
    """
    Chat request payload.
    """

    message: str = Field(
        ...,
        min_length=1,
        max_length=20_000,
    )

    history: list[dict[str, str]] = Field(
        default_factory=list,
    )


class WebSearchRequest(BaseModel):
    """
    Web search request payload.
    """

    query: str = Field(
        ...,
        min_length=1,
        max_length=500,
    )

    limit: int = Field(
        default=8,
        ge=1,
        le=15,
    )


class CodeSearchRequest(BaseModel):
    """
    Codebase search request payload.
    """

    query: str = Field(
        ...,
        min_length=1,
        max_length=500,
    )

    path: str = Field(
        default=".",
        max_length=500,
    )

    limit: int = Field(
        default=100,
        ge=1,
        le=200,
    )


class FileReadRequest(BaseModel):
    """
    File inspection request payload.
    """

    path: str = Field(
        ...,
        min_length=1,
        max_length=500,
    )


@router.get(
    "/status",
)
async def workspace_status():
    """
    Return real Smart BethG workspace status.
    """

    return get_workspace_status()


@router.get(
    "/provider",
)
async def workspace_provider():
    """
    Return safe AI provider status.
    """

    return provider_status()


@router.post(
    "/chat",
)
async def workspace_chat(
    payload: ChatRequest,
):
    """
    Send a message to the configured AI runtime.
    """

    try:

        result = generate_response(
            user_message=payload.message,
            history=payload.history,
        )

        return {
            "ok": True,
            "message": result["content"],
            "provider": result["provider"],
            "model": result["model"],
        }

    except AIProviderNotConfigured as exc:

        return {
            "ok": False,
            "error_type": "provider_not_configured",
            "message": str(exc),
        }

    except AIRuntimeError as exc:

        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc

    except ValueError as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@router.post(
    "/search",
)
async def workspace_search(
    payload: WebSearchRequest,
):
    """
    Search the public web.
    """

    try:

        return search_web(
            query=payload.query,
            limit=payload.limit,
        )

    except SearchServiceError as exc:

        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc

    except ValueError as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@router.get(
    "/codebase",
)
async def workspace_codebase():
    """
    Return a structural project summary.
    """

    try:

        return inspect_project()

    except CodebaseServiceError as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@router.get(
    "/codebase/files",
)
async def workspace_codebase_files(
    path: str = ".",
    limit: int = 500,
):
    """
    List project files.
    """

    try:

        return list_files(
            relative_path=path,
            limit=max(
                1,
                min(limit, 1000),
            ),
        )

    except CodebaseServiceError as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@router.post(
    "/codebase/search",
)
async def workspace_codebase_search(
    payload: CodeSearchRequest,
):
    """
    Search project source files.
    """

    try:

        return search_code(
            query=payload.query,
            relative_path=payload.path,
            limit=payload.limit,
        )

    except CodebaseServiceError as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except ValueError as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@router.post(
    "/codebase/read",
)
async def workspace_codebase_read(
    payload: FileReadRequest,
):
    """
    Read one source/text file.
    """

    try:

        return read_file(
            relative_path=payload.path,
        )

    except CodebaseServiceError as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except ValueError as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc
