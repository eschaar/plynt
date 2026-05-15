"""Cache middleware for Plynth transport chains.

Provides ``CacheMiddleware`` and ``AsyncCacheMiddleware``, which plug any
``CacheBackend`` (from ``plynth.base.cache``) into the transport middleware
chain (ADR-0010, ADR-0013).

Both classes share ``_CacheBase``, which owns the backend reference and the
cache-read / cache-write helpers. Only the ``handle`` method differs between
the sync and async variants.

Usage::

    from plynth.middleware.cache import CacheMiddleware
    from plynth.cache import LocMemCache
    from plynth.http.transport import HttpxSyncTransport

    transport = HttpxSyncTransport(
        middlewares=[CacheMiddleware(LocMemCache())],
    )

"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from http import HTTPStatus

from plynth.base.cache import CacheBackend
from plynth.base.request import Request
from plynth.base.response import AsyncStreamingResponse, Response, StreamingResponse

__all__ = ["AsyncCacheMiddleware", "CacheMiddleware"]


class _CacheBase:
    """Shared state and cache logic for CacheMiddleware / AsyncCacheMiddleware.

    Not intended for direct use. Subclass ``CacheMiddleware`` or
    ``AsyncCacheMiddleware`` instead.
    """

    def __init__(self, backend: CacheBackend, ttl: float | None = None) -> None:
        """Initialize _CacheBase."""
        self._backend = backend
        self._ttl = ttl

    @staticmethod
    def _snapshot_response(response: Response) -> Response:
        """Return an immutable snapshot copy of a response for cache safety."""
        return Response(
            status_code=response.status_code,
            headers=dict(response.headers),
            content=bytes(response.content),
        )

    def _get_cached(self, request: Request) -> Response | None:
        """Return cached response for GET requests, or ``None`` on miss or non-GET."""
        if request.stream:
            return None
        if request.method != "GET":
            return None
        key = type(self._backend).cache_key(request)
        cached = self._backend.get(key)
        if cached is None:
            return None
        if not isinstance(cached, Response):
            raise TypeError("Cached value must be Response")
        return self._snapshot_response(cached)

    def _store(self, request: Request, response: Response) -> None:
        """Store response for successful GET requests only (status < 400)."""
        if request.stream:
            return
        if isinstance(response, (StreamingResponse, AsyncStreamingResponse)):
            return
        if request.method == "GET" and response.status_code < HTTPStatus.BAD_REQUEST:
            key = type(self._backend).cache_key(request)
            self._backend.set(key, self._snapshot_response(response), self._ttl)


class CacheMiddleware(_CacheBase):
    """Synchronous cache middleware for GET response caching.

    On a GET request checks the backend before calling the next handler.
    On a cache hit, returns the cached response without touching the
    network.  On a miss, calls the next handler and stores any successful
    (< 400) response.

    Only GET requests are cached.  Error responses (status ≥ 400) are
    never stored.

    Args:
        backend: Any ``CacheBackend``-compatible object.
        ttl: Optional time-to-live in seconds passed to ``backend.set()``
            on every cache write.  Backends that do not support TTL ignore
            this value.

    Example::

        transport = HttpxSyncTransport(
            middlewares=[CacheMiddleware(LocMemCache(), ttl=300)],
        )

    """

    def handle(
        self,
        request: Request,
        next_handler: Callable[[Request], Response],
    ) -> Response:
        """Return a cached response or delegate to the next handler.

        Returns:
            A cached response on a GET hit, or the result of calling
            ``next_handler``.

        """
        cached = self._get_cached(request)
        if cached is not None:
            return cached
        response = next_handler(request)
        self._store(request, response)
        return response


class AsyncCacheMiddleware(_CacheBase):
    """Asynchronous cache middleware for GET response caching.

    The async counterpart of ``CacheMiddleware``.  The ``CacheBackend``
    protocol is synchronous; only the ``handle`` method is a coroutine.

    Args:
        backend: Any ``CacheBackend``-compatible object.
        ttl: Optional time-to-live in seconds passed to ``backend.set()``
            on every cache write.  Backends that do not support TTL ignore
            this value.

    Example::

        transport = HttpxAsyncTransport(
            middlewares=[AsyncCacheMiddleware(LocMemCache(), ttl=300)],
        )

    """

    async def handle(
        self,
        request: Request,
        next_handler: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Return a cached response or delegate to the next handler.

        Returns:
            A cached response on a GET hit, or the result of awaiting
            ``next_handler``.

        """
        cached = self._get_cached(request)
        if cached is not None:
            return cached
        response = await next_handler(request)
        self._store(request, response)
        return response
