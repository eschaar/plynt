"""Provide DRF error-mapping helpers for plynt exceptions"""

from __future__ import annotations

import importlib
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
    "map_exception_to_drf_response",
    "plynt_exception_handler",
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
    """Resolve HTTP status for known plynt base errors

    Uses ``isinstance`` matching so subclasses inherit parent mapping.
    """
    for error_type, status_code in _BASE_ERROR_STATUS_MAP.items():
        if isinstance(exc, error_type):
            return status_code
    return 500


def build_error_payload(
    exc: Exception,
    *,
    include_details: bool = False,
) -> dict[str, Any]:
    """Build safe external error payload from an exception

    Args:
        exc: Raised exception.
        include_details: Include ``details`` when the exception is a
            ``BaseError`` and details are available.

    Returns:
        JSON-serializable payload suitable for DRF responses

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
    """Convert exception into DRF ``Response`` object

    Args:
        exc: Raised exception.
        include_details: Include plynt error ``details`` in the payload.

    Returns:
        DRF ``Response`` instance with mapped status and payload

    """
    response_mod = importlib.import_module("rest_framework.response")
    response_cls = response_mod.Response

    status_code = 500
    if isinstance(exc, HttpStatusError):
        status_code = exc.status_code
    elif isinstance(exc, BaseError):
        status_code = _status_code_for_base_error(exc)

    payload = build_error_payload(exc, include_details=include_details)
    return response_cls(payload, status=status_code)


def plynt_exception_handler(exc: Exception, context: dict[str, Any]) -> Any:
    """Handle plynt exceptions with DRF fallback behavior

    First delegates to DRF's default exception handler. When DRF does not map
    the exception, this returns a mapped plynt error response.
    """
    views_mod = importlib.import_module("rest_framework.views")
    drf_exception_handler = views_mod.exception_handler

    drf_response = drf_exception_handler(exc, context)
    if drf_response is not None:
        return drf_response

    return map_exception_to_drf_response(exc)
