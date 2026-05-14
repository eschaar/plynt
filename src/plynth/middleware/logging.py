"""Logging middleware for Plynth services.

This module provides HTTP logging middleware:

- ``LoggingMiddleware`` — sync middleware that logs every request/response
  at ``INFO`` level, including elapsed time. Subclass and override
  ``_log_request``/``_log_response`` to customise.
- ``AsyncLoggingMiddleware`` — async counterpart of ``LoggingMiddleware``.

Filters and formatter live in ``plynth.log``:

- ``ThrottleLogs``, ``ExceptionInfoFilter``, ``PlynthHTTPFilter`` —
  ``plynth.log.filters``
- ``StructuredFormatter`` — ``plynth.log.formatter``

Logger hierarchy:

- ``plynth.base`` — retry attempts, auth refreshes (DEBUG / WARNING).
- ``plynth.http.transport`` — per-request send/receive events (DEBUG).
- ``plynth.http`` — INFO-level request/response timing logging
  (when ``LoggingMiddleware`` or ``AsyncLoggingMiddleware`` is installed,
  shares the namespace with ``plynth.http.transport`` debug lines).

Usage example::

    import logging
    from plynth.log import PlynthHTTPFilter, StructuredFormatter
    from plynth.middleware.logging import LoggingMiddleware
    from plynth.http.transport import HttpxSyncTransport

    handler = logging.StreamHandler()
    handler.setFormatter(StructuredFormatter())
    handler.addFilter(PlynthHTTPFilter())
    logging.getLogger("plynth").addHandler(handler)
    logging.getLogger("plynth").setLevel(logging.INFO)

    transport = HttpxSyncTransport(middlewares=[LoggingMiddleware()])
"""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from plynth.base.request import Request
from plynth.base.response import AsyncStreamingResponse, Response, StreamingResponse

__all__ = [
    "AsyncLoggingMiddleware",
    "LoggingMiddleware",
]

_SENSITIVE_QUERY_KEYS: frozenset[str] = frozenset(
    {
        "access_token",
        "apikey",
        "api_key",
        "authorization",
        "code",
        "password",
        "secret",
        "token",
    }
)


def _scrub_url(url: str) -> str:
    """Return URL with sensitive query parameter values redacted."""
    split = urlsplit(url)
    if not split.query:
        return url

    redacted_query: list[tuple[str, str]] = []
    for key, value in parse_qsl(split.query, keep_blank_values=True):
        if key.lower() in _SENSITIVE_QUERY_KEYS:
            redacted_query.append((key, "[REDACTED]"))
        else:
            redacted_query.append((key, value))

    return urlunsplit(
        (
            split.scheme,
            split.netloc,
            split.path,
            urlencode(redacted_query),
            split.fragment,
        )
    )


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------


class _LoggingBase:
    """Shared state and formatting logic for logging middleware.

    Not intended for direct use. Subclass ``LoggingMiddleware`` or
    ``AsyncLoggingMiddleware`` instead.
    """

    def __init__(
        self,
        *,
        logger: logging.Logger | None = None,
        level: int = logging.INFO,
    ) -> None:
        """Initialise the middleware.

        Args:
            logger: Logger to emit records on. Defaults to ``plynth.http``,
                placing HTTP-level events in the same namespace as the
                transport (``plynth.http.transport``).
            level: Log level for request and response records.
                Defaults to ``logging.INFO``.

        """
        self._logger = logger or logging.getLogger("plynth.http")
        self._level = level

    def _log_request(self, request: Request) -> float:
        """Emit a log record for the outgoing request and return the start time."""
        safe_url = _scrub_url(str(request.url))
        self._logger.log(
            self._level,
            "--> %s %s",
            request.method,
            safe_url,
            extra={
                "event.action": "http-request",
                "http.request.method": request.method,
                "url.full": safe_url,
            },
        )
        return time.monotonic()

    def _log_response(self, request: Request, response: Response, start: float) -> None:
        """Emit a log record for the received response, including elapsed time."""
        safe_url = _scrub_url(str(request.url))
        elapsed_ms = (time.monotonic() - start) * 1000
        elapsed_ns = int(elapsed_ms * 1_000_000)
        stream_suffix = (
            " (streaming)"
            if isinstance(response, (StreamingResponse, AsyncStreamingResponse))
            else ""
        )
        self._logger.log(
            self._level,
            "<-- %d %s %s%s  (%.0fms)",
            response.status_code,
            request.method,
            safe_url,
            stream_suffix,
            elapsed_ms,
            extra={
                "event.action": "http-request",
                "event.duration": elapsed_ns,
                "http.request.method": request.method,
                "http.response.status_code": response.status_code,
                "url.full": safe_url,
            },
        )


class LoggingMiddleware(_LoggingBase):
    """Synchronous middleware that logs every request and response at INFO.

    Satisfies the ``SyncMiddleware`` protocol. Install it on any
    ``BaseSyncTransport`` via the ``middlewares`` constructor argument.

    Both ``_log_request`` and ``_log_response`` are protected methods
    designed for overriding in subclasses.

    Args:
        logger: Logger to use. Defaults to the module logger
            (``plynth.middleware.logging``).
        level: Log level. Defaults to ``logging.INFO``.

    Example::

        transport = HttpxSyncTransport(middlewares=[LoggingMiddleware()])

    """

    def handle(
        self,
        request: Request,
        next_handler: Callable[[Request], Response],
    ) -> Response:
        """Log the request, call the next handler, log the response."""
        start = self._log_request(request)
        response = next_handler(request)
        self._log_response(request, response, start)
        return response


class AsyncLoggingMiddleware(_LoggingBase):
    """Asynchronous middleware that logs every request and response at INFO.

    Async counterpart of ``LoggingMiddleware``. Satisfies the
    ``AsyncMiddleware`` protocol.

    Args:
        logger: Logger to use. Defaults to the module logger
            (``plynth.middleware.logging``).
        level: Log level. Defaults to ``logging.INFO``.

    Example::

        transport = HttpxAsyncTransport(middlewares=[AsyncLoggingMiddleware()])

    """

    async def handle(
        self,
        request: Request,
        next_handler: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Log the request, await the next handler, log the response."""
        start = self._log_request(request)
        response = await next_handler(request)
        self._log_response(request, response, start)
        return response
