"""FastAPI request-header propagation helpers for Plynt."""

from __future__ import annotations

from collections.abc import Mapping

from plynt.middleware.header import (
    AsyncHeaderMiddleware,
    HeaderMiddleware,
    HeaderValue,
)

__all__ = [
    "DEFAULT_HEADER_MAP",
    "DEFAULT_SENSITIVE_HEADER_DENYLIST",
    "build_async_request_header_middleware",
    "build_request_header_middleware",
]

DEFAULT_HEADER_MAP: dict[str, str] = {
    "X-Request-Id": "X-Request-Id",
    "X-Correlation-Id": "X-Correlation-Id",
    "traceparent": "traceparent",
    "tracestate": "tracestate",
}

_DEFAULT_SENSITIVE_HEADER_NAMES = """
authorization
proxy-authorization
cookie
set-cookie
x-api-key
""".split()

DEFAULT_SENSITIVE_HEADER_DENYLIST: frozenset[str] = frozenset(
    _DEFAULT_SENSITIVE_HEADER_NAMES
)


def _normalize_header_name(name: str) -> str:
    """Normalize header names for case-insensitive matching."""
    return name.strip().lower()


def _read_incoming_header(request: object, header_name: str) -> str | None:
    """Read one inbound header value from request-like objects."""
    request_headers = getattr(request, "headers", None)
    if not isinstance(request_headers, Mapping):
        return None

    value = request_headers.get(header_name)
    if isinstance(value, str) and value:
        return value

    lowered = {str(k).lower(): v for k, v in request_headers.items()}
    lowered_value = lowered.get(header_name.lower())
    return lowered_value if isinstance(lowered_value, str) and lowered_value else None


def build_request_header_middleware(
    request: object,
    headers: dict[str, str] | None = None,
    *,
    deny_headers: set[str] | None = None,
) -> HeaderMiddleware:
    """Build sync middleware that forwards selected inbound request headers.

    Args:
        request: FastAPI request-like object containing inbound ``headers``.
        headers: Optional mapping of outbound header name to inbound header
            name. When omitted, a default correlation/tracing set is used.
        deny_headers: Optional case-insensitive denylist for inbound/outbound
            header names. Defaults to sensitive auth/session headers.

    Returns:
        ``HeaderMiddleware`` configured with resolved static header values.

    """
    return HeaderMiddleware(
        _resolve_request_headers(
            request,
            headers=headers,
            deny_headers=deny_headers,
        )
    )


def build_async_request_header_middleware(
    request: object,
    headers: dict[str, str] | None = None,
    *,
    deny_headers: set[str] | None = None,
) -> AsyncHeaderMiddleware:
    """Build async middleware that forwards selected inbound request headers.

    Args:
        request: FastAPI request-like object containing inbound ``headers``.
        headers: Optional mapping of outbound header name to inbound header
            name. When omitted, a default correlation/tracing set is used.
        deny_headers: Optional case-insensitive denylist for inbound/outbound
            header names. Defaults to sensitive auth/session headers.

    Returns:
        ``AsyncHeaderMiddleware`` configured with resolved static header values.

    """
    return AsyncHeaderMiddleware(
        _resolve_request_headers(
            request,
            headers=headers,
            deny_headers=deny_headers,
        )
    )


def _resolve_request_headers(
    request: object,
    *,
    headers: dict[str, str] | None,
    deny_headers: set[str] | None,
) -> dict[str, HeaderValue]:
    """Resolve outbound headers from one inbound request object."""
    header_map = headers or DEFAULT_HEADER_MAP
    denied = (
        {_normalize_header_name(name) for name in deny_headers}
        if deny_headers is not None
        else DEFAULT_SENSITIVE_HEADER_DENYLIST
    )
    resolved_headers: dict[str, HeaderValue] = {}

    for outbound_name, inbound_name in header_map.items():
        if _normalize_header_name(outbound_name) in denied:
            continue
        if _normalize_header_name(inbound_name) in denied:
            continue

        inbound_value = _read_incoming_header(request, inbound_name)
        if inbound_value is not None:
            resolved_headers[outbound_name] = inbound_value

    return resolved_headers
