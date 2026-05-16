"""Abstract base classes for sync and async transports (ADR-0013).

Two-tier transport hierarchy:

**Tier 1 — Abstract contracts** (``SyncTransport`` / ``AsyncTransport``):
  Minimal ABCs that define only ``send()``. Use these for test doubles
  or protocol transports (gRPC, etc.) that manage their own cross-cutting
  concerns.

**Tier 2 — Abstract base with cross-cutting concerns**
  (``BaseSyncTransport`` / ``BaseAsyncTransport``):
  Concrete ``send()`` that composes a **middleware chain** and delegates to
  ``_send_once()``. Subclass these for any HTTP transport and implement
  only ``_send_once()`` with the actual network I/O.

Authentication and retry are first-class middleware (ADR-0011, ADR-0013):

::

    middlewares = [CacheMiddleware, HeaderMiddleware, AuthMiddleware, RetryMiddleware]
        → _send_once

Each middleware receives the request and a ``next_handler`` callable. It
may short-circuit (e.g. cache hit) or pass through. The first middleware
in the list is outermost.

Usage — simple mock::

    class MockSyncTransport(SyncTransport):
        def send(self, request: Request) -> Response:
            return Response(status_code=200)

Usage — real HTTP transport::

    class MyHttpTransport(BaseSyncTransport):
        def _send_once(self, request: Request) -> Response:
            # Pure network I/O here; no auth, retry, or cache logic.
            ...

Transports are injected into clients; never use global state.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable

from plynth.base.middleware import AsyncMiddleware, SyncMiddleware
from plynth.base.request import Request
from plynth.base.response import Response

__all__ = [
    "AsyncTransport",
    "BaseAsyncTransport",
    "BaseSyncTransport",
    "SyncTransport",
]


class SyncTransport(ABC):
    """Contract for synchronous transports.

    Implement this class to provide a sync transport backed by any HTTP
    library (e.g. ``requests``, ``httpx``), or a non-HTTP protocol (e.g.
    gRPC) that manages its own auth and retry.

    Extension:
        - Subclass and implement ``send()``.
        - For HTTP transports with shared auth/retry/cache, extend
          ``BaseSyncTransport`` and implement ``_send_once()`` instead.
    """

    @abstractmethod
    def send(self, request: Request) -> Response:  # pragma: no cover
        """Send a request synchronously and return the raw response."""


class AsyncTransport(ABC):
    """Contract for asynchronous transports.

    Implement this class to provide an async transport backed by any HTTP
    library (e.g. ``httpx``, ``aiohttp``), or a non-HTTP protocol that
    manages its own auth and retry.

    Extension:
        - Subclass and implement ``send()``.
        - For HTTP transports with shared auth/retry/cache, extend
          ``BaseAsyncTransport`` and implement ``_send_once()`` instead.
    """

    @abstractmethod
    async def send(self, request: Request) -> Response:  # pragma: no cover
        """Send a request asynchronously and return the raw response."""


class BaseSyncTransport(SyncTransport):
    """Abstract base transport with middleware chain support.

    Subclass this and implement ``_send_once()`` with the actual network I/O.
    All cross-cutting concerns (auth, retry, caching) are handled by
    middleware. Pass them as ``middlewares`` in the constructor or
    ``from_settings()``.

    ``send()`` builds a middleware chain around ``_send_once`` (ADR-0013).
    Each middleware wraps the next; the first entry is outermost.

    Args:
        middlewares: Optional list of sync middleware. Common choices:
            ``CacheMiddleware``, ``BearerTokenAuthMiddleware``,
            ``OAuth2AuthMiddleware``, ``RetryMiddleware``.

    Note:
        ``from_settings()`` is a **convention**, not an abstract method.
        Each concrete subclass implements it with its own settings type
        (e.g. ``HttpxSyncTransport.from_settings(settings: HTTPSettings)``).
        Making it abstract would violate LSP because each subclass requires
        a different settings type.

    Example::

        class MyTransport(BaseSyncTransport):
            def _send_once(self, request: Request) -> Response:
                # Only network I/O here.
                ...

        from plynth.http.middleware.auth import BearerTokenAuthMiddleware
        from plynth.middleware.retry import RetryMiddleware
        from plynth.http.policies import HttpRetryPolicy

        transport = MyTransport(
            middlewares=[
                BearerTokenAuthMiddleware("secret"),
                RetryMiddleware(HttpRetryPolicy(max_attempts=3)),
            ]
        )

    """

    def __init__(
        self,
        *,
        middlewares: list[SyncMiddleware] | None = None,
    ) -> None:
        """Initialise the base transport with optional middleware."""
        self._middlewares: list[SyncMiddleware] = (
            list(middlewares) if middlewares else []
        )

    def send(self, request: Request) -> Response:
        """Send a request through the middleware chain.

        Builds the middleware chain around ``_send_once`` and invokes it.
        The first middleware is outermost.

        Returns:
            The response from the server (or from a short-circuiting
            middleware such as ``CacheMiddleware``).

        """
        chain = self._build_middleware_chain(self._send_once)
        return chain(request)

    def _build_middleware_chain(
        self,
        innermost: Callable[[Request], Response],
    ) -> Callable[[Request], Response]:
        """Compose middleware layers around the innermost handler, outermost first."""
        handler: Callable[[Request], Response] = innermost
        for mw in reversed(self._middlewares):

            def _step(
                req: Request,
                _mw: SyncMiddleware = mw,
                _next: Callable[[Request], Response] = handler,
            ) -> Response:
                """Handle step."""
                return _mw.handle(req, _next)

            handler = _step
        return handler

    @abstractmethod
    def _send_once(self, request: Request) -> Response:  # pragma: no cover
        """Execute a single raw network call — no retry, auth, or caching.

        Subclasses implement **only** the actual network I/O here; all
        cross-cutting concerns belong in middleware.

        """


class BaseAsyncTransport(AsyncTransport):
    """Abstract base async transport with middleware chain support.

    Async counterpart of ``BaseSyncTransport``. Subclass and implement
    ``_send_once()`` with the actual async network I/O.

    Args:
        middlewares: Optional list of async middleware. Common choices:
            ``AsyncCacheMiddleware``, ``AsyncBearerTokenAuthMiddleware``,
            ``AsyncRetryMiddleware``.

    """

    def __init__(
        self,
        *,
        middlewares: list[AsyncMiddleware] | None = None,
    ) -> None:
        """Initialise the base async transport."""
        self._middlewares: list[AsyncMiddleware] = (
            list(middlewares) if middlewares else []
        )

    async def send(self, request: Request) -> Response:
        """Send a request asynchronously through the middleware chain.

        Builds the middleware chain around ``_send_once`` and awaits the
        result. The first middleware is outermost.

        Returns:
            The response from the server (or from a short-circuiting
            middleware such as ``AsyncCacheMiddleware``).

        """
        chain = self._build_middleware_chain(self._send_once)
        return await chain(request)

    def _build_middleware_chain(
        self,
        innermost: Callable[[Request], Awaitable[Response]],
    ) -> Callable[[Request], Awaitable[Response]]:
        """Compose middleware layers around the innermost handler, outermost first."""
        handler: Callable[[Request], Awaitable[Response]] = innermost
        for mw in reversed(self._middlewares):

            async def _step(
                req: Request,
                _mw: AsyncMiddleware = mw,
                _next: Callable[[Request], Awaitable[Response]] = handler,
            ) -> Response:
                """Handle step."""
                return await _mw.handle(req, _next)

            handler = _step
        return handler

    @abstractmethod
    async def _send_once(self, request: Request) -> Response:  # pragma: no cover
        """Execute a single raw async network call — no retry, auth, or caching.

        Async counterpart of ``BaseSyncTransport._send_once``. Subclasses
        implement **only** the actual network I/O here.

        """
