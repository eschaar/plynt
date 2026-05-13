"""Middleware protocols for the **transport** layer.

All middleware in Plynth operates at the **transport level**, not the service
level. Each middleware wraps the next via a ``handle(request, next_handler)``
call, forming a chain of responsibility where control flows inward through each
layer before returning outward with the response (the "onion" model).

Middleware fires exactly once per logical request, regardless of how many retry
attempts are made internally by the transport.

The middleware layer is **not** a service-level interceptor. It has access
only to the raw ``Request`` and ``Response`` objects (URL, headers, status
code, body). Business-level context — domain identifiers, user context,
operation names — is not available here and belongs in the service layer
itself.

Typical transport-level uses:

- Logging every outgoing call at ``INFO`` level (see
  ``plynth.middleware.logging.LoggingMiddleware``).
- Caching GET responses (see ``plynth.middleware.cache.CacheMiddleware``).
- Timing requests.
- Injecting or inspecting headers.
- Circuit breaking (count errors, short-circuit before the network).

Sync example::

    from plynth.middleware.logging import LoggingMiddleware
    from plynth.http.transport import HttpxSyncTransport

    transport = HttpxSyncTransport(middlewares=[LoggingMiddleware()])

Async example::

    from plynth.middleware.logging import AsyncLoggingMiddleware
    from plynth.http.transport import HttpxAsyncTransport

    transport = HttpxAsyncTransport(middlewares=[AsyncLoggingMiddleware()])

Middleware ordering — the first entry in the list is outermost (called first
entering, last exiting). This is the standard Django/ASGI/Express convention::

    middlewares = [A, B, C]

    # Execution order:
    # A.handle (enter) → B.handle (enter) → C.handle (enter)
    #   → _dispatch_request
    # C.handle (exit) → B.handle (exit) → A.handle (exit)

"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Protocol, runtime_checkable

from plynth.base.request import Request
from plynth.base.response import Response

__all__ = ["AsyncMiddleware", "NextAsyncHandler", "NextSyncHandler", "SyncMiddleware"]

NextSyncHandler = Callable[[Request], Response]
NextAsyncHandler = Callable[[Request], Awaitable[Response]]


@runtime_checkable
class SyncMiddleware(Protocol):
    """Protocol for synchronous transport middleware.

    Each middleware receives the outgoing request and a ``next_handler``
    callable representing the rest of the chain. The middleware may:

    - Inspect or mutate the request before calling ``next_handler``.
    - Short-circuit by returning a ``Response`` without calling
      ``next_handler`` (e.g. cache hit, circuit breaker).
    - Inspect or transform the response after calling ``next_handler``.

    Example — timing middleware::

        import logging
        import time

        logger = logging.getLogger(__name__)

        class SyncTimingMiddleware:
            def handle(
                self,
                request: Request,
                next_handler: Callable[[Request], Response],
            ) -> Response:
                start = time.monotonic()
                response = next_handler(request)
                elapsed = time.monotonic() - start
                logger.info(
                    "%s %s took %.3fs", request.method, request.url, elapsed
                )
                return response

    """

    def handle(self, request: Request, next_handler: NextSyncHandler) -> Response:
        """Process the request and return a response.

        The middleware may inspect or mutate the request before calling
        ``next_handler``, or short-circuit by returning a ``Response`` directly.

        """
        ...  # pragma: no cover


@runtime_checkable
class AsyncMiddleware(Protocol):
    """Protocol for asynchronous transport middleware.

    The async counterpart of ``SyncMiddleware``. The ``handle`` method is
    a coroutine that receives the request and an async ``next_handler``.

    Example — async timing middleware::

        import logging
        import time

        logger = logging.getLogger(__name__)

        class AsyncTimingMiddleware:
            async def handle(
                self,
                request: Request,
                next_handler: Callable[[Request], Awaitable[Response]],
            ) -> Response:
                start = time.monotonic()
                response = await next_handler(request)
                elapsed = time.monotonic() - start
                logger.info(
                    "%s %s took %.3fs", request.method, request.url, elapsed
                )
                return response

    """

    async def handle(
        self,
        request: Request,
        next_handler: NextAsyncHandler,
    ) -> Response:
        """Process the request asynchronously and return a response.

        The middleware may inspect or mutate the request before awaiting
        ``next_handler``, or short-circuit by returning a ``Response`` directly.

        """
        ...  # pragma: no cover
