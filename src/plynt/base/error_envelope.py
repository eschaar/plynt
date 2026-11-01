"""Build framework-independent external error envelopes (ADR-0040)"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable, Mapping

from plynt.base.errors import BaseError

__all__ = ["ErrorEnvelope", "build_error_envelope", "default_error_envelope"]

ErrorEnvelope = Callable[[Exception, int, str | None], Mapping[str, object]]

_logger = logging.getLogger(__name__)


def default_error_envelope(
    exc: Exception,
    status_code: int,
    request_id: str | None,
    *,
    include_details: bool = False,
) -> dict[str, object]:
    """Build the existing message/code payload without diagnostic context

    Args:
        status_code: Status selected by the caller; not included by default.
        request_id: Scoped ID supplied by the caller; not included by default.
        include_details: Include explicitly opted-in BaseError details.
            Applications must ensure these are safe and JSON-serializable.

    """
    if isinstance(exc, BaseError):
        payload: dict[str, object] = {
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


def build_error_envelope(
    exc: Exception,
    status_code: int,
    request_id: str | None,
    *,
    envelope: ErrorEnvelope | None = None,
    include_details: bool = False,
) -> dict[str, object]:
    """Build a custom envelope or fall back to the existing error payload

    Args:
        status_code: Status selected by the caller, without core status mapping.
        request_id: Scoped ID passed to the custom callable without generation.
        envelope: Callable returning a JSON-serializable mapping with string
            keys. Failures or invalid output are logged without exception
            details, then replaced by the default payload.
        include_details: Include BaseError details in the default payload.
            A custom callable owns its entire payload and ignores this flag.

    """
    if envelope is not None:
        try:
            result = envelope(exc, status_code, request_id)
            if not isinstance(result, Mapping):
                raise TypeError("Error envelope must return a mapping")
            payload = dict(result)
            if not all(isinstance(key, str) for key in payload):
                raise TypeError("Error envelope keys must be strings")
            json.dumps(payload, allow_nan=False)
            return payload
        except Exception:
            # Callback failures must not leak exception messages or payloads.
            _logger.error("Custom error envelope failed; using default error payload")
    return default_error_envelope(
        exc, status_code, request_id, include_details=include_details
    )
