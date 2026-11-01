"""Tests for circuit breaker middleware."""

# pylint: disable=protected-access

from __future__ import annotations

import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor

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

    def test_older_request_cannot_release_another_probe(
        self, monotonic_clock: MonotonicClock
    ) -> None:
        """Keep the live probe reserved when an older closed-state request fails"""
        monotonic_clock.bind("plynt.middleware.circuit_breaker")
        mw = CircuitBreakerMiddleware(
            CircuitBreakerPolicy(
                failure_threshold=1,
                recovery_timeout=1,
                failure_status_codes=frozenset({503}),
            )
        )
        old_entered, probe_entered = threading.Event(), threading.Event()
        release_old, release_probe = threading.Event(), threading.Event()

        def old_request(request: Request) -> Response:
            old_entered.set()
            assert release_old.wait(5)
            raise ValueError("ignored")

        def probe(request: Request) -> Response:
            probe_entered.set()
            assert release_probe.wait(5)
            return Response(status_code=200)

        with ThreadPoolExecutor(max_workers=2) as pool:
            try:
                old = pool.submit(mw.handle, _REQUEST, old_request)
                assert old_entered.wait(5)
                mw.handle(_REQUEST, lambda req: Response(status_code=503))
                monotonic_clock.advance(1)
                current = pool.submit(mw.handle, _REQUEST, probe)
                assert probe_entered.wait(5)
                release_old.set()
                with pytest.raises(ValueError):
                    old.result(timeout=5)
                with pytest.raises(CircuitBreakerOpenError):
                    mw.handle(_REQUEST, lambda req: Response(status_code=200))
            finally:
                release_old.set()
                release_probe.set()
            assert current.result(timeout=5).status_code == 200

    @pytest.mark.parametrize(
        ("error", "count_network_errors"),
        [
            (ValueError("ignored"), True),
            (ValueError("ignored"), False),
            (TimeoutError("disabled"), False),
            (KeyboardInterrupt(), True),
            (SystemExit(), True),
        ],
    )
    def test_ignored_exception_releases_probe(
        self,
        monotonic_clock: MonotonicClock,
        error: BaseException,
        count_network_errors: bool,
    ) -> None:
        """Release ignored probes without counting or treating them as success"""
        monotonic_clock.bind("plynt.middleware.circuit_breaker")
        mw = CircuitBreakerMiddleware(
            CircuitBreakerPolicy(
                failure_threshold=1,
                recovery_timeout=1,
                failure_status_codes=frozenset({503}),
                count_network_errors=count_network_errors,
            )
        )
        mw.handle(_REQUEST, lambda req: Response(status_code=503))
        monotonic_clock.advance(1)

        def fail(request: Request) -> Response:
            raise error

        for _ in range(2):
            with pytest.raises(type(error)) as caught:
                mw.handle(_REQUEST, fail)
            assert caught.value is error
            assert mw._state._state == "half-open"
            assert mw._state._failure_count == 0

        assert (
            mw.handle(_REQUEST, lambda req: Response(status_code=200)).status_code
            == 200
        )
        assert mw._state._state == "closed"

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

        def _before_call(*, now: float) -> float | None:
            calls.append("before")
            assert mw._lock.locked()
            return original_before_call(now=now)

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

        def _after_exception(
            exc: BaseException, *, now: float, probe_opened_at: float | None
        ) -> None:
            calls.append(type(exc).__name__)
            assert mw._lock.locked()
            original_after_exception(exc, now=now, probe_opened_at=probe_opened_at)

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

    @pytest.mark.parametrize("old_half_open", [False, True])
    async def test_older_request_cannot_release_another_probe(
        self, monotonic_clock: MonotonicClock, old_half_open: bool
    ) -> None:
        """Keep a live probe reserved across closed requests and recovery waves"""
        monotonic_clock.bind("plynt.middleware.circuit_breaker")
        mw = AsyncCircuitBreakerMiddleware(
            CircuitBreakerPolicy(
                failure_threshold=1,
                recovery_timeout=1,
                half_open_max_calls=2,
                failure_status_codes=frozenset({503}),
            )
        )
        old_entered, probe_entered = asyncio.Event(), asyncio.Event()
        release_old, release_probe = asyncio.Event(), asyncio.Event()

        async def old_request(request: Request) -> Response:
            old_entered.set()
            await release_old.wait()
            raise ValueError("ignored")

        async def unavailable(request: Request) -> Response:
            return Response(status_code=503)

        async def probe(request: Request) -> Response:
            probe_entered.set()
            await release_probe.wait()
            return Response(status_code=200)

        if old_half_open:
            await mw.handle(_REQUEST, unavailable)
            monotonic_clock.advance(1)
        old = asyncio.create_task(mw.handle(_REQUEST, old_request))
        current: list[asyncio.Task[Response]] = []
        try:
            await old_entered.wait()
            await mw.handle(_REQUEST, unavailable)
            monotonic_clock.advance(1)
            for _ in range(2):
                probe_entered.clear()
                current.append(asyncio.create_task(mw.handle(_REQUEST, probe)))
                await probe_entered.wait()
            release_old.set()
            with pytest.raises(ValueError):
                await old
            with pytest.raises(CircuitBreakerOpenError):
                await mw.handle(_REQUEST, unavailable)
        finally:
            release_old.set()
            release_probe.set()
            await asyncio.gather(old, *current, return_exceptions=True)

    @pytest.mark.parametrize(
        ("error", "count_network_errors"),
        [
            (ValueError("ignored"), True),
            (ValueError("ignored"), False),
            (TimeoutError("disabled"), False),
            (KeyboardInterrupt(), True),
            (SystemExit(), True),
            (asyncio.CancelledError(), True),
        ],
    )
    async def test_ignored_exception_releases_probe(
        self,
        monotonic_clock: MonotonicClock,
        error: BaseException,
        count_network_errors: bool,
    ) -> None:
        """Release ignored async probes and preserve the original exception"""
        monotonic_clock.bind("plynt.middleware.circuit_breaker")
        mw = AsyncCircuitBreakerMiddleware(
            CircuitBreakerPolicy(
                failure_threshold=1,
                recovery_timeout=1,
                failure_status_codes=frozenset({503}),
                count_network_errors=count_network_errors,
            )
        )

        async def unavailable(request: Request) -> Response:
            return Response(status_code=503)

        async def fail(request: Request) -> Response:
            raise error

        async def success(request: Request) -> Response:
            return Response(status_code=200)

        await mw.handle(_REQUEST, unavailable)
        monotonic_clock.advance(1)
        for _ in range(2):
            with pytest.raises(type(error)) as caught:
                await mw.handle(_REQUEST, fail)
            assert caught.value is error
            assert mw._state._state == "half-open"
            assert mw._state._failure_count == 0

        assert (await mw.handle(_REQUEST, success)).status_code == 200
        assert mw._state._state == "closed"

    async def test_cancelled_task_releases_half_open_probe(
        self, monotonic_clock: MonotonicClock
    ) -> None:
        """Allow another probe after cancellation of an in-flight task"""
        monotonic_clock.bind("plynt.middleware.circuit_breaker")
        mw = AsyncCircuitBreakerMiddleware(
            CircuitBreakerPolicy(
                failure_threshold=1,
                recovery_timeout=1,
                failure_status_codes=frozenset({503}),
            )
        )

        async def unavailable(request: Request) -> Response:
            return Response(status_code=503)

        entered = asyncio.Event()

        async def blocked(request: Request) -> Response:
            entered.set()
            await asyncio.Event().wait()
            return Response(status_code=200)

        await mw.handle(_REQUEST, unavailable)
        monotonic_clock.advance(1)
        task = asyncio.create_task(mw.handle(_REQUEST, blocked))
        await entered.wait()
        with pytest.raises(CircuitBreakerOpenError):
            await mw.handle(_REQUEST, unavailable)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

        # A classified failure must still reopen after the slot is released.
        assert (await mw.handle(_REQUEST, unavailable)).status_code == 503
        with pytest.raises(CircuitBreakerOpenError) as caught:
            await mw.handle(_REQUEST, unavailable)
        assert caught.value.retry_after_seconds == 1

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
