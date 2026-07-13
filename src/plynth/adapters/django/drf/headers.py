"""DRF request-header propagation helpers for Plynth."""

from __future__ import annotations

from collections.abc import Mapping

from plynth.middleware.header import HeaderMiddleware, HeaderValue

__all__ = ["build_request_header_middleware"]

DEFAULT_HEADER_MAP: dict[str, str] = {
    "X-Request-Id": "X-Request-Id",
    "X-Correlation-Id": "X-Correlation-Id",
    "traceparent": "traceparent",
    "tracestate": "tracestate",
}


def _read_incoming_header(request: object, header_name: str) -> str | None:
    """Read one inbound header value from a DRF/Django request-like object."""
    request_headers = getattr(request, "headers", None)
    if not isinstance(request_headers, Mapping):
        return None

    value = request_headers.get(header_name)
    if isinstance(value, str) and value:
        return value

    # Fallback for plain dict-like objects without case-insensitive lookup.
    lowered = {str(k).lower(): v for k, v in request_headers.items()}
    lowered_value = lowered.get(header_name.lower())
    return lowered_value if isinstance(lowered_value, str) and lowered_value else None


def build_request_header_middleware(
    request: object,
    headers: dict[str, str] | None = None,
) -> HeaderMiddleware:
    """Build middleware that forwards selected inbound request headers.

    Args:
        request: DRF/Django request object containing inbound ``headers``.
        headers: Optional mapping of outbound header name to inbound header
            name. When omitted, a default correlation/tracing set is used.

    Returns:
        ``HeaderMiddleware`` configured with resolved static header values.

    """
    header_map = headers or DEFAULT_HEADER_MAP
    resolved_headers: dict[str, HeaderValue] = {}

    for outbound_name, inbound_name in header_map.items():
        inbound_value = _read_incoming_header(request, inbound_name)
        if inbound_value is not None:
            resolved_headers[outbound_name] = inbound_value

    return HeaderMiddleware(resolved_headers)
