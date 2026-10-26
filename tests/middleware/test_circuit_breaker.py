"""Tests for circuit breaker middleware."""

# pylint: disable=protected-access

from __future__ import annotations

import pytest

from plynt.base.middleware import AsyncMiddleware, SyncMiddleware
from plynt.base.policies import CircuitBreakerPolicy
from plynt.base.request import Request
from plynt.base.response import Response
from plynt.middleware.circuit_breaker import (
    AsyncCircuitBreakerMiddleware,
    CircuitBreakerMiddleware,
    CircuitBreakerOpenError,
)
from tests.conftest import MonotonicClock

_REQUEST = Request(method="GET", url="https://example.com")


class TestCircuitBreakerMiddleware:
    """Tests for the synchronous circuit breaker middleware."""

    def test_satisfies_sync_middleware_protocol(self) -> None:
        """Validate middleware satisfies SyncMiddleware protocol."""
        mw = CircuitBreakerMiddleware(CircuitBreakerPolicy())
        assert isinstance(mw, SyncMiddleware)

    def test_opens_after_consecutive_exceptions(
        self,
        monotonic_clock: MonotonicClock,
    ) -> None:
        """Validate breaker opens after configured consecutive failures."""
        monotonic_clock.bind("plynt.middleware.circuit_breaker")

        mw = CircuitBreakerMiddleware(CircuitBreakerPolicy(failure_threshold=2))

        with pytest.raises(TimeoutError):
            mw.handle(_REQUEST, lambda req: (_ for _ in ()).throw(TimeoutError("x")))
        with pytest.raises(TimeoutError):
            mw.handle(_REQUEST, lambda req: (_ for _ in ()).throw(TimeoutError("x")))

        with pytest.raises(CircuitBreakerOpenError):
            mw.handle(_REQUEST, lambda req: Response(status_code=200, content=b"ok"))

    @pytest.mark.parametrize("elapsed", [5.0, 5.1], ids=["at-boundary", "after"])
    def test_half_open_probe_closes_on_success(
        self,
        monotonic_clock: MonotonicClock,
        elapsed: float,
    ) -> None:
        """Validate half-open probe closes breaker after successful call."""
        monotonic_clock.bind("plynt.middleware.circuit_breaker")

        policy = CircuitBreakerPolicy(failure_threshold=1, recovery_timeout=5.0)
        mw = CircuitBreakerMiddleware(policy)

        with pytest.raises(TimeoutError):
            mw.handle(_REQUEST, lambda req: (_ for _ in ()).throw(TimeoutError("x")))

        monotonic_clock.advance(4.9)
        with pytest.raises(CircuitBreakerOpenError):
            mw.handle(_REQUEST, lambda req: Response(status_code=200, content=b"ok"))

        monotonic_clock.advance(elapsed - 4.9)
        result = mw.handle(
            _REQUEST,
            lambda req: Response(status_code=200, content=b"ok"),
        )
        assert result.status_code == 200

        result2 = mw.handle(
            _REQUEST,
            lambda req: Response(status_code=201, content=b"ok"),
        )
        assert result2.status_code == 201

    def test_opens_on_failure_status_code(
        self,
        monotonic_clock: MonotonicClock,
    ) -> None:
        """Validate configured failure status code opens breaker."""
        monotonic_clock.bind("plynt.middleware.circuit_breaker")

        policy = CircuitBreakerPolicy(
            failure_threshold=1,
            failure_status_codes=frozenset({503}),
        )
        mw = CircuitBreakerMiddleware(policy)

        first = mw.handle(
            _REQUEST,
            lambda req: Response(status_code=503, content=b"bad"),
        )
        assert first.status_code == 503

        with pytest.raises(CircuitBreakerOpenError):
            mw.handle(_REQUEST, lambda req: Response(status_code=200, content=b"ok"))

    def test_before_and_after_response_hold_lock(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Validate sync state updates run while the middleware lock is held."""
        mw = CircuitBreakerMiddleware(CircuitBreakerPolicy())
        calls: list[str] = []

        original_before_call = mw._state.before_call
        original_after_response = mw._state.after_response

        def _before_call(*, now: float) -> None:
            calls.append("before")
            assert mw._lock.locked()
            original_before_call(now=now)

        def _after_response(response: Response, *, now: float) -> None:
            calls.append("after_response")
            assert mw._lock.locked()
            original_after_response(response, now=now)

        monkeypatch.setattr(mw._state, "before_call", _before_call)
        monkeypatch.setattr(mw._state, "after_response", _after_response)

        result = mw.handle(
            _REQUEST, lambda req: Response(status_code=200, content=b"ok")
        )

        assert result.status_code == 200
        assert calls == ["before", "after_response"]

    def test_after_exception_holds_lock(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Validate sync exception updates run while the middleware lock is held."""
        mw = CircuitBreakerMiddleware(CircuitBreakerPolicy())
        calls: list[str] = []

        original_after_exception = mw._state.after_exception

        def _after_exception(exc: BaseException, *, now: float) -> None:
            calls.append(type(exc).__name__)
            assert mw._lock.locked()
            original_after_exception(exc, now=now)

        monkeypatch.setattr(mw._state, "after_exception", _after_exception)

        with pytest.raises(TimeoutError):
            mw.handle(_REQUEST, lambda req: (_ for _ in ()).throw(TimeoutError("x")))

        assert calls == ["TimeoutError"]

    def test_half_open_probe_failure_reopens_breaker(
        self,
        monotonic_clock: MonotonicClock,
    ) -> None:
        """Validate a failing probe in half-open transitions circuit back to open."""
        monotonic_clock.bind("plynt.middleware.circuit_breaker")

        policy = CircuitBreakerPolicy(failure_threshold=1, recovery_timeout=5.0)
        mw = CircuitBreakerMiddleware(policy)

        with pytest.raises(TimeoutError):
            mw.handle(_REQUEST, lambda req: (_ for _ in ()).throw(TimeoutError("x")))

        monotonic_clock.advance(5.1)

        with pytest.raises(TimeoutError):
            mw.handle(_REQUEST, lambda req: (_ for _ in ()).throw(TimeoutError("x")))

        with pytest.raises(CircuitBreakerOpenError) as exc_info:
            mw.handle(_REQUEST, lambda req: Response(status_code=200, content=b"ok"))
        assert exc_info.value.retry_after_seconds > 0.0

    def test_half_open_rejects_excess_probes(
        self,
        monkeypatch: pytest.MonkeyPatch,
        monotonic_clock: MonotonicClock,
    ) -> None:
        """Validate half-open state rejects calls beyond max_calls limit."""
        monotonic_clock.bind("plynt.middleware.circuit_breaker")

        policy = CircuitBreakerPolicy(failure_threshold=1, recovery_timeout=5.0)
        mw = CircuitBreakerMiddleware(policy)

        with pytest.raises(TimeoutError):
            mw.handle(_REQUEST, lambda req: (_ for _ in ()).throw(TimeoutError("x")))

        monotonic_clock.advance(5.1)

        # Prevent state reset so the circuit stays half-open after the first probe
        monkeypatch.setattr(mw._state, "record_success", lambda: None)

        mw.handle(_REQUEST, lambda req: Response(status_code=200, content=b"ok"))

        with pytest.raises(CircuitBreakerOpenError) as exc_info:
            mw.handle(_REQUEST, lambda req: Response(status_code=200, content=b"ok"))
        assert exc_info.value.retry_after_seconds == 0.0


class TestAsyncCircuitBreakerMiddleware:
    """Tests for the asynchronous circuit breaker middleware."""

    def test_satisfies_async_middleware_protocol(self) -> None:
        """Validate middleware satisfies AsyncMiddleware protocol."""
        mw = AsyncCircuitBreakerMiddleware(CircuitBreakerPolicy())
        assert isinstance(mw, AsyncMiddleware)

    @pytest.mark.asyncio
    async def test_opens_after_consecutive_exceptions(
        self,
        monotonic_clock: MonotonicClock,
    ) -> None:
        """Validate async breaker opens after configured failures."""
        monotonic_clock.bind("plynt.middleware.circuit_breaker")

        mw = AsyncCircuitBreakerMiddleware(CircuitBreakerPolicy(failure_threshold=2))

        async def failing(_: Request) -> Response:
            raise TimeoutError("x")

        with pytest.raises(TimeoutError):
            await mw.handle(_REQUEST, failing)
        with pytest.raises(TimeoutError):
            await mw.handle(_REQUEST, failing)

        with pytest.raises(CircuitBreakerOpenError):
            await mw.handle(_REQUEST, lambda req: _async_response(200))

    @pytest.mark.asyncio
    @pytest.mark.parametrize("elapsed", [5.0, 5.1], ids=["at-boundary", "after"])
    async def test_half_open_probe_closes_on_success(
        self,
        monotonic_clock: MonotonicClock,
        elapsed: float,
    ) -> None:
        """Validate async half-open probe closes breaker on success."""
        monotonic_clock.bind("plynt.middleware.circuit_breaker")

        policy = CircuitBreakerPolicy(failure_threshold=1, recovery_timeout=5.0)
        mw = AsyncCircuitBreakerMiddleware(policy)

        async def failing(_: Request) -> Response:
            raise TimeoutError("x")

        with pytest.raises(TimeoutError):
            await mw.handle(_REQUEST, failing)

        monotonic_clock.advance(4.9)
        with pytest.raises(CircuitBreakerOpenError):
            await mw.handle(_REQUEST, lambda req: _async_response(200))

        monotonic_clock.advance(elapsed - 4.9)
        result = await mw.handle(_REQUEST, lambda req: _async_response(200))
        assert result.status_code == 200

    @pytest.mark.asyncio
    async def test_opens_on_failure_status_code(
        self,
        monotonic_clock: MonotonicClock,
    ) -> None:
        """Validate async breaker opens on configured failure status."""
        monotonic_clock.bind("plynt.middleware.circuit_breaker")

        policy = CircuitBreakerPolicy(
            failure_threshold=1,
            failure_status_codes=frozenset({503}),
        )
        mw = AsyncCircuitBreakerMiddleware(policy)

        first = await mw.handle(_REQUEST, lambda req: _async_response(503))
        assert first.status_code == 503

        with pytest.raises(CircuitBreakerOpenError):
            await mw.handle(_REQUEST, lambda req: _async_response(200))

    @pytest.mark.asyncio
    async def test_half_open_probe_failure_reopens_breaker(
        self,
        monotonic_clock: MonotonicClock,
    ) -> None:
        """Validate a failing async probe in half-open transitions circuit to open."""
        monotonic_clock.bind("plynt.middleware.circuit_breaker")

        policy = CircuitBreakerPolicy(failure_threshold=1, recovery_timeout=5.0)
        mw = AsyncCircuitBreakerMiddleware(policy)

        async def failing(_: Request) -> Response:
            raise TimeoutError("x")

        with pytest.raises(TimeoutError):
            await mw.handle(_REQUEST, failing)

        monotonic_clock.advance(5.1)

        with pytest.raises(TimeoutError):
            await mw.handle(_REQUEST, failing)

        with pytest.raises(CircuitBreakerOpenError) as exc_info:
            await mw.handle(_REQUEST, lambda req: _async_response(200))
        assert exc_info.value.retry_after_seconds > 0.0

    @pytest.mark.asyncio
    async def test_half_open_rejects_excess_probes(
        self,
        monkeypatch: pytest.MonkeyPatch,
        monotonic_clock: MonotonicClock,
    ) -> None:
        """Validate async half-open state rejects calls beyond max_calls limit."""
        monotonic_clock.bind("plynt.middleware.circuit_breaker")

        policy = CircuitBreakerPolicy(failure_threshold=1, recovery_timeout=5.0)
        mw = AsyncCircuitBreakerMiddleware(policy)

        async def failing(_: Request) -> Response:
            raise TimeoutError("x")

        with pytest.raises(TimeoutError):
            await mw.handle(_REQUEST, failing)

        monotonic_clock.advance(5.1)

        # Prevent state reset so the circuit stays half-open after the first probe
        monkeypatch.setattr(mw._state, "record_success", lambda: None)

        await mw.handle(_REQUEST, lambda req: _async_response(200))

        with pytest.raises(CircuitBreakerOpenError) as exc_info:
            await mw.handle(_REQUEST, lambda req: _async_response(200))
        assert exc_info.value.retry_after_seconds == 0.0


async def _async_response(status_code: int) -> Response:
    """Return async response helper."""
    return Response(status_code=status_code, content=b"ok")
