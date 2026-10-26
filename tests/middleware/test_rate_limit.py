"""Tests for rate-limit middleware."""

from __future__ import annotations

import pytest

from plynt.base.middleware import AsyncMiddleware, SyncMiddleware
from plynt.base.policies import RateLimitPolicy
from plynt.base.request import Request
from plynt.base.response import Response
from plynt.middleware.rate_limit import (
    AsyncRateLimitMiddleware,
    RateLimitExceededError,
    RateLimitMiddleware,
)
from tests.conftest import MonotonicClock

_REQUEST = Request(method="GET", url="https://example.com")


class TestRateLimitMiddleware:
    """Tests for synchronous rate-limit middleware."""

    def test_satisfies_sync_middleware_protocol(self) -> None:
        """Validate middleware satisfies SyncMiddleware protocol."""
        mw = RateLimitMiddleware(RateLimitPolicy(max_requests=2, window_seconds=1.0))
        assert isinstance(mw, SyncMiddleware)

    def test_rejects_when_window_limit_reached(
        self,
        monotonic_clock: MonotonicClock,
    ) -> None:
        """Validate sync middleware rejects requests above window limit."""
        monotonic_clock.bind("plynt.middleware.rate_limit")

        mw = RateLimitMiddleware(RateLimitPolicy(max_requests=2, window_seconds=10.0))

        first = mw.handle(
            _REQUEST,
            lambda req: Response(status_code=200, content=b"1"),
        )
        second = mw.handle(
            _REQUEST,
            lambda req: Response(status_code=200, content=b"2"),
        )
        assert first.status_code == 200
        assert second.status_code == 200

        with pytest.raises(RateLimitExceededError):
            mw.handle(_REQUEST, lambda req: Response(status_code=200, content=b"3"))

    @pytest.mark.parametrize("elapsed", [5.0, 5.1], ids=["at-boundary", "after"])
    def test_allows_again_after_window_passes(
        self,
        monotonic_clock: MonotonicClock,
        elapsed: float,
    ) -> None:
        """Validate sync middleware allows requests after window expires."""
        monotonic_clock.bind("plynt.middleware.rate_limit")

        mw = RateLimitMiddleware(RateLimitPolicy(max_requests=1, window_seconds=5.0))

        mw.handle(_REQUEST, lambda req: Response(status_code=200, content=b"1"))
        with pytest.raises(RateLimitExceededError):
            mw.handle(_REQUEST, lambda req: Response(status_code=200, content=b"2"))

        monotonic_clock.advance(4.9)
        with pytest.raises(RateLimitExceededError):
            mw.handle(_REQUEST, lambda req: Response(status_code=200, content=b"2"))

        monotonic_clock.advance(elapsed - 4.9)
        result = mw.handle(
            _REQUEST,
            lambda req: Response(status_code=201, content=b"3"),
        )
        assert result.status_code == 201

    def test_acquire_runs_while_lock_is_held(self) -> None:
        """Validate sync rate-limit state updates run while the lock is held."""
        mw = RateLimitMiddleware(RateLimitPolicy(max_requests=1, window_seconds=5.0))
        calls: list[float] = []
        window = vars(mw)["_window"]
        lock = vars(mw)["_lock"]

        original_acquire = window.acquire

        def _acquire(*, now: float) -> None:
            calls.append(now)
            assert lock.locked()
            original_acquire(now=now)

        window.acquire = _acquire

        result = mw.handle(
            _REQUEST, lambda req: Response(status_code=200, content=b"ok")
        )

        assert result.status_code == 200
        assert len(calls) == 1


class TestAsyncRateLimitMiddleware:
    """Tests for asynchronous rate-limit middleware."""

    def test_satisfies_async_middleware_protocol(self) -> None:
        """Validate middleware satisfies AsyncMiddleware protocol."""
        mw = AsyncRateLimitMiddleware(
            RateLimitPolicy(max_requests=2, window_seconds=1.0)
        )
        assert isinstance(mw, AsyncMiddleware)

    @pytest.mark.asyncio
    async def test_rejects_when_window_limit_reached(
        self,
        monotonic_clock: MonotonicClock,
    ) -> None:
        """Validate async middleware rejects requests above window limit."""
        monotonic_clock.bind("plynt.middleware.rate_limit")

        mw = AsyncRateLimitMiddleware(
            RateLimitPolicy(max_requests=2, window_seconds=10.0)
        )

        first = await mw.handle(_REQUEST, lambda req: _async_response(200))
        second = await mw.handle(_REQUEST, lambda req: _async_response(200))
        assert first.status_code == 200
        assert second.status_code == 200

        with pytest.raises(RateLimitExceededError):
            await mw.handle(_REQUEST, lambda req: _async_response(200))

    @pytest.mark.asyncio
    @pytest.mark.parametrize("elapsed", [5.0, 5.1], ids=["at-boundary", "after"])
    async def test_allows_again_after_window_passes(
        self,
        monotonic_clock: MonotonicClock,
        elapsed: float,
    ) -> None:
        """Validate async middleware allows requests after window expires."""
        monotonic_clock.bind("plynt.middleware.rate_limit")

        mw = AsyncRateLimitMiddleware(
            RateLimitPolicy(max_requests=1, window_seconds=5.0)
        )

        await mw.handle(_REQUEST, lambda req: _async_response(200))
        with pytest.raises(RateLimitExceededError):
            await mw.handle(_REQUEST, lambda req: _async_response(200))

        monotonic_clock.advance(4.9)
        with pytest.raises(RateLimitExceededError):
            await mw.handle(_REQUEST, lambda req: _async_response(200))

        monotonic_clock.advance(elapsed - 4.9)
        result = await mw.handle(_REQUEST, lambda req: _async_response(201))
        assert result.status_code == 201


async def _async_response(status_code: int) -> Response:
    """Return async response helper."""
    return Response(status_code=status_code, content=b"ok")
