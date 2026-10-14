"""Tests for SyncMiddleware and AsyncMiddleware Protocols."""

from __future__ import annotations

from collections.abc import Callable

from plynt.base.middleware import (
    AsyncMiddleware,
    NextAsyncHandler,
    NextSyncHandler,
    SyncMiddleware,
)
from plynt.base.request import Request
from plynt.base.response import Response

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _request() -> Request:
    """Handle request."""
    return Request(method="GET", url="https://api.example.com/items")


def _response(status_code: int = 200) -> Response:
    """Handle response."""
    return Response(status_code=status_code)


def _next(response: Response) -> NextSyncHandler:
    """Return a sync next_handler that always returns *response*."""

    def handler(request: Request) -> Response:
        """Return handler."""
        return response

    return handler


async def _async_next_fn(request: Request) -> Response:
    """Handle async next fn."""
    return _response()


# ---------------------------------------------------------------------------
# SyncMiddleware
# ---------------------------------------------------------------------------


class TestSyncMiddleware:
    """Test suite for SyncMiddleware."""

    def test_object_with_handle_satisfies_protocol(self) -> None:
        """Validate object with handle satisfies protocol."""

        class TimingMiddleware:
            """Represent TimingMiddleware."""

            def handle(
                self, request: Request, next_handler: NextSyncHandler
            ) -> Response:
                """Return handle."""
                return next_handler(request)

        assert isinstance(TimingMiddleware(), SyncMiddleware)

    def test_object_without_handle_does_not_satisfy_protocol(self) -> None:
        """Validate object without handle does not satisfy protocol."""

        class Incomplete:
            """Represent Incomplete."""

            def before_send(self, request: Request) -> None:
                """Return before send."""
                pass

        assert not isinstance(Incomplete(), SyncMiddleware)

    def test_empty_object_does_not_satisfy_protocol(self) -> None:
        """Validate empty object does not satisfy protocol."""

        class Empty:
            """Represent Empty."""

            pass

        assert not isinstance(Empty(), SyncMiddleware)

    def test_handle_is_called_with_request_and_next_handler(self) -> None:
        """Validate handle is called with request and next handler."""
        received: list[tuple[Request, Callable[..., Response]]] = []

        class CapturingMiddleware:
            """Represent CapturingMiddleware."""

            def handle(
                self, request: Request, next_handler: NextSyncHandler
            ) -> Response:
                """Return handle."""
                received.append((request, next_handler))
                return next_handler(request)

        req = _request()
        resp = _response(200)
        mw = CapturingMiddleware()
        result = mw.handle(req, _next(resp))
        assert len(received) == 1
        assert received[0][0] is req
        assert result is resp

    def test_handle_can_short_circuit(self) -> None:
        """Validate handle can short circuit."""
        cached = _response(200)

        class CacheHitMiddleware:
            """Represent CacheHitMiddleware."""

            def handle(
                self, request: Request, next_handler: NextSyncHandler
            ) -> Response:
                """Return handle."""
                return cached  # never calls next_handler

        calls: list[int] = []

        def counting_next(r: Request) -> Response:
            """Return counting next."""
            calls.append(1)
            return _response(500)

        mw = CacheHitMiddleware()
        result = mw.handle(_request(), counting_next)
        assert result is cached
        assert calls == []

    def test_handle_can_mutate_request(self) -> None:
        """Validate handle can mutate request."""

        class HeaderInjector:
            """Represent HeaderInjector."""

            def handle(
                self, request: Request, next_handler: NextSyncHandler
            ) -> Response:
                """Return handle."""
                request.headers["X-Injected"] = "yes"
                return next_handler(request)

        seen: list[Request] = []

        def capturing_next(r: Request) -> Response:
            """Return capturing next."""
            seen.append(r)
            return _response()

        req = _request()
        HeaderInjector().handle(req, capturing_next)
        assert seen[0].headers["X-Injected"] == "yes"


# ---------------------------------------------------------------------------
# AsyncMiddleware
# ---------------------------------------------------------------------------


class TestAsyncMiddleware:
    """Test suite for AsyncMiddleware."""

    def test_object_with_async_handle_satisfies_protocol(self) -> None:
        """Validate object with async handle satisfies protocol."""

        class AsyncTimingMiddleware:
            """Represent AsyncTimingMiddleware."""

            async def handle(
                self, request: Request, next_handler: NextAsyncHandler
            ) -> Response:
                """Return handle."""
                return await next_handler(request)

        assert isinstance(AsyncTimingMiddleware(), AsyncMiddleware)

    def test_sync_handle_also_satisfies_async_protocol(self) -> None:
        # runtime_checkable only checks attribute presence, not whether
        # the method is a coroutine. This test documents that limitation.
        """Validate sync handle also satisfies async protocol."""

        class SyncHandleOnly:
            """Represent SyncHandleOnly."""

            def handle(
                self, request: Request, next_handler: NextSyncHandler
            ) -> Response:
                """Return handle."""
                return next_handler(request)

        assert isinstance(SyncHandleOnly(), AsyncMiddleware)

    def test_object_without_handle_does_not_satisfy_protocol(self) -> None:
        """Validate object without handle does not satisfy protocol."""

        class Incomplete:
            """Represent Incomplete."""

            async def before_send(self, request: Request) -> None:
                """Return before send."""
                pass

        assert not isinstance(Incomplete(), AsyncMiddleware)

    def test_empty_object_does_not_satisfy_protocol(self) -> None:
        """Validate empty object does not satisfy protocol."""

        class Empty:
            """Represent Empty."""

            pass

        assert not isinstance(Empty(), AsyncMiddleware)

    async def test_handle_is_awaitable(self) -> None:
        """Validate handle is awaitable."""
        received: list[Request] = []

        class CapturingMiddleware:
            """Represent CapturingMiddleware."""

            async def handle(
                self, request: Request, next_handler: NextAsyncHandler
            ) -> Response:
                """Return handle."""
                received.append(request)
                return await next_handler(request)

        req = _request()
        mw = CapturingMiddleware()
        result = await mw.handle(req, _async_next_fn)
        assert received == [req]
        assert result.status_code == 200

    async def test_handle_can_short_circuit_async(self) -> None:
        """Validate handle can short circuit async."""
        cached = _response(200)

        class AsyncCacheHitMiddleware:
            """Represent AsyncCacheHitMiddleware."""

            async def handle(
                self, request: Request, next_handler: NextAsyncHandler
            ) -> Response:
                """Return handle."""
                return cached

        calls: list[int] = []

        async def counting_next(r: Request) -> Response:
            """Return counting next."""
            calls.append(1)
            return _response(500)

        result = await AsyncCacheHitMiddleware().handle(_request(), counting_next)
        assert result is cached
        assert calls == []
