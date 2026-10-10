"""
Smart BethG - Error Handling

Two problems this fixes:

1. Before this, an unhandled exception in a route would either bubble up
   as FastAPI's default (a bare traceback in dev, or a generic
   "Internal Server Error" plain-text page in production - exactly what
   the very first live deploy bug looked like from the outside).
2. Error response shape was inconsistent between routes - some returned
   {"error": ...}, others {"detail": ...}, others nothing structured.

This module makes every error response (validation, HTTP exceptions, and
truly unexpected exceptions) come back as:

    {"error": {"message": str, "type": str, "status_code": int}}

and logs full details (including traceback for unexpected exceptions)
server-side via smart_bethg.error, without ever putting internals
(stack traces, file paths, query text) in the response the client sees.
"""
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from logging_setup import get_logger

logger = get_logger("error")


def _error_body(message: str, error_type: str, status_code: int) -> dict:
    return {"error": {"message": message, "type": error_type, "status_code": status_code}}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(request: Request, exc: StarletteHTTPException):
        # 401/403/404/429 etc. - expected, application-raised. Logged at
        # a lower level since these are normal control flow, not bugs.
        logger.info(
            "HTTP %s on %s %s: %s",
            exc.status_code, request.method, request.url.path, exc.detail,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_body(str(exc.detail), "http_error", exc.status_code),
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError):
        logger.info("Validation error on %s %s: %s", request.method, request.url.path, exc.errors())
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_error_body("The request was invalid.", "validation_error", 422),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_exception(request: Request, exc: Exception):
        # Truly unexpected - a real bug. Full traceback goes to the log
        # (exc_info=True), never to the response.
        logger.error(
            "Unhandled exception on %s %s", request.method, request.url.path, exc_info=True
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_error_body(
                "Something went wrong on our end. Please try again.",
                "internal_error",
                500,
            ),
        )
