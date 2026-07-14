"""DRF error-mapping helpers for plynth exceptions."""

from __future__ import annotations

import importlib
from typing import Any

from plynth.base.errors import BaseError
from plynth.http.errors import HttpStatusError

__all__ = [
    "build_error_payload",
    "map_exception_to_drf_response",
    "plynth_exception_handler",
]


def build_error_payload(
    exc: Exception,
    *,
    include_details: bool = False,
) -> dict[str, Any]:
    """Build a safe external error payload from an exception.

    Args:
        exc: Raised exception.
        include_details: Include ``details`` when the exception is a
            ``BaseError`` and details are available.

    Returns:
        A JSON-serializable payload suitable for DRF responses.

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


def map_exception_to_drf_response(
    exc: Exception,
    *,
    include_details: bool = False,
) -> Any:
    """Convert an exception into a DRF ``Response`` object.

    Args:
        exc: Raised exception.
        include_details: Include plynth error ``details`` in the payload.

    Returns:
        DRF ``Response`` instance with mapped status and payload.

    """
    response_mod = importlib.import_module("rest_framework.response")
    response_cls = response_mod.Response

    status_code = 500
    if isinstance(exc, HttpStatusError):
        status_code = exc.status_code

    payload = build_error_payload(exc, include_details=include_details)
    return response_cls(payload, status=status_code)


def plynth_exception_handler(exc: Exception, context: dict[str, Any]) -> Any:
    """Fallback-aware DRF exception handler for plynth-backed views.

    First delegates to DRF's default exception handler. When DRF does not map
    the exception, this returns a mapped plynth error response.
    """
    views_mod = importlib.import_module("rest_framework.views")
    drf_exception_handler = views_mod.exception_handler

    drf_response = drf_exception_handler(exc, context)
    if drf_response is not None:
        return drf_response

    return map_exception_to_drf_response(exc)
