"""FastAPI error-mapping helpers for plynt exceptions."""

from __future__ import annotations

import importlib
from collections.abc import Awaitable, Callable
from typing import Any

from plynt.base.errors import (
    BaseError,
    ConfigurationError,
    DependencyUnavailableError,
    FeatureDisabledError,
    InvalidInputError,
    OperationFailedError,
    TransportError,
)
from plynt.http.errors import HttpStatusError

__all__ = [
    "build_error_payload",
    "create_plynt_exception_handler",
    "install_plynt_exception_handlers",
    "map_exception_to_fastapi_response",
]


_BASE_ERROR_STATUS_MAP: dict[type[BaseError], int] = {
    InvalidInputError: 400,
    OperationFailedError: 422,
    FeatureDisabledError: 503,
    DependencyUnavailableError: 503,
    ConfigurationError: 500,
    TransportError: 502,
}


def _status_code_for_base_error(exc: BaseError) -> int:
    """Resolve HTTP status for known plynt base errors."""
    for error_type, status_code in _BASE_ERROR_STATUS_MAP.items():
        if isinstance(exc, error_type):
            return status_code
    return 500


def build_error_payload(
    exc: Exception,
    *,
    include_details: bool = False,
) -> dict[str, Any]:
    """Build safe external error payload from an exception.

    Args:
        exc: Raised exception.
        include_details: Include ``details`` when the exception is a
            ``BaseError`` and details are available.

    Returns:
        JSON-serializable payload suitable for FastAPI responses.

    """
    if isinstance(exc, BaseError):
        payload: dict[str, Any] = {
            "message": exc.message,
            "code": exc.code or "INTERNAL_SERVER_ERROR",
        }
        if include_details and exc.details is not None:
            payload["details"] = exc.details
        return payload

    return {
        "message": "Internal server error",
        "code": "INTERNAL_SERVER_ERROR",
    }


def map_exception_to_fastapi_response(
    exc: Exception,
    *,
    include_details: bool = False,
) -> Any:
    """Convert exception into a FastAPI JSON response object.

    Args:
        exc: Raised exception.
        include_details: Include plynt error ``details`` in the payload.

    Returns:
        FastAPI ``JSONResponse`` with mapped status and payload.

    """
    fastapi_responses = importlib.import_module("fastapi.responses")
    json_response = fastapi_responses.JSONResponse

    status_code = 500
    if isinstance(exc, HttpStatusError):
        status_code = exc.status_code
    elif isinstance(exc, BaseError):
        status_code = _status_code_for_base_error(exc)

    payload = build_error_payload(exc, include_details=include_details)
    return json_response(payload, status_code=status_code)


def create_plynt_exception_handler(
    *,
    include_details: bool = False,
) -> Callable[[object, Exception], Awaitable[Any]]:
    """Create FastAPI-compatible async exception handler for plynt errors."""

    async def _handler(_: object, exc: Exception) -> Any:
        return map_exception_to_fastapi_response(
            exc,
            include_details=include_details,
        )

    return _handler


def install_plynt_exception_handlers(
    app: object,
    *,
    include_details: bool = False,
) -> None:
    """Install plynt exception handlers on a FastAPI app.

    Registers handlers for ``BaseError`` and ``HttpStatusError``.

    Args:
        app: FastAPI app-like object exposing ``add_exception_handler``.
        include_details: Include plynt ``details`` in external payloads.

    """
    add_exception_handler = getattr(app, "add_exception_handler", None)
    if add_exception_handler is None:
        raise RuntimeError("FastAPI app object must expose add_exception_handler")

    handler = create_plynt_exception_handler(include_details=include_details)
    add_exception_handler(BaseError, handler)
    add_exception_handler(HttpStatusError, handler)
