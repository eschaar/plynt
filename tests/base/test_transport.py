"""Tests for BaseSyncTransport and BaseAsyncTransport.

Covers: retry loop (backoff, status-code-based retry, network-error
retry), middleware chain, and _send_once delegation.

Auth tests have moved to tests/http/test_auth.py (auth is now
first-class middleware, not a transport constructor argument).
Cache middleware tests have moved to tests/middleware/test_cache.py.

Uses lightweight fakes rather than mocking the httpx2 layer.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest

from plynth.base.middleware import NextAsyncHandler
from plynth.base.policies import RetryPolicy
from plynth.base.request import Request
from plynth.base.response import Response
from plynth.base.transport import BaseAsyncTransport, BaseSyncTransport
from plynth.http.policies import HttpRetryPolicy
from plynth.middleware.retry import AsyncRetryMiddleware, RetryMiddleware

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _req(method: str = "GET", url: str = "https://example.com") -> Request:
    """Handle req."""
    return Request(method=method, url=url)


def _resp(status: int = 200) -> Response:
    """Handle resp."""
    return Response(status_code=status, content=b"{}")


class _StubSyncTransport(BaseSyncTransport):
    """Concrete transport for testing; returns responses from a queue."""

    def __init__(self, responses: list[Response], **kwargs: object) -> None:
        """Initialize _StubSyncTransport."""
        super().__init__(**kwargs)  # type: ignore[arg-type]
        self._responses = list(responses)
        self.calls: int = 0

    def _send_once(self, request: Request) -> Response:
        """Handle send once."""
        self.calls += 1
        return self._responses.pop(0)


class _ErrorSyncTransport(BaseSyncTransport):
    """Transport that raises on ``_send_once()`` a configurable number of times."""

    def __init__(
        self,
        fail_times: int,
        success_response: Response,
        exc: Exception | None = None,
        **kwargs: object,
    ) -> None:
        """Initialize _ErrorSyncTransport."""
        super().__init__(**kwargs)  # type: ignore[arg-type]
        self._fail_times = fail_times
        self._success = success_response
        self._exc = exc or ConnectionError("network failure")
        self.calls: int = 0

    def _send_once(self, request: Request) -> Response:
        """Handle send once."""
        self.calls += 1
        if self.calls <= self._fail_times:
            raise self._exc
        return self._success


class _StubAsyncTransport(BaseAsyncTransport):
    """Async concrete transport for testing."""

    def __init__(self, responses: list[Response], **kwargs: object) -> None:
        """Initialize _StubAsyncTransport."""
        super().__init__(**kwargs)  # type: ignore[arg-type]
        self._responses = list(responses)
        self.calls: int = 0

    async def _send_once(self, request: Request) -> Response:
        """Handle send once."""
        self.calls += 1
        return self._responses.pop(0)


class _ErrorAsyncTransport(BaseAsyncTransport):
    """Async transport that raises on ``_send_once()`` a set number of
    times."""

    def __init__(
        self,
        fail_times: int,
        success_response: Response,
        exc: Exception | None = None,
        **kwargs: object,
    ) -> None:
        """Initialize _ErrorAsyncTransport."""
        super().__init__(**kwargs)  # type: ignore[arg-type]
        self._fail_times = fail_times
        self._success = success_response
        self._exc = exc or ConnectionError("network failure")
        self.calls: int = 0

    async def _send_once(self, request: Request) -> Response:
        """Handle send once."""
        self.calls += 1
        if self.calls <= self._fail_times:
            raise self._exc
        return self._success


# ---------------------------------------------------------------------------
# BaseSyncTransport — basic send
# ---------------------------------------------------------------------------


class TestBaseSyncTransportSend:
    """Test suite for BaseSyncTransportSend."""

    def test_delegates_to_send_once(self) -> None:
        """Validate delegates to send once."""
        transport = _StubSyncTransport([_resp(200)])
        resp = transport.send(_req())
        assert resp.status_code == 200
        assert transport.calls == 1

    def test_is_abstract_without_send_once(self) -> None:
        """Validate is abstract without send once."""
        with pytest.raises(TypeError):
            BaseSyncTransport()  # type: ignore  # pylint: disable=abstract-class-instantiated


# ---------------------------------------------------------------------------
# Retry
# ---------------------------------------------------------------------------


class TestBaseSyncTransportRetry:
    """Test suite for BaseSyncTransportRetry."""

    def test_no_retry_without_retry_middleware(self) -> None:
        """Validate no retry without retry middleware."""
        transport = _StubSyncTransport([_resp(503)])
        resp = transport.send(_req())
        assert resp.status_code == 503
        assert transport.calls == 1

    def test_no_retry_when_max_attempts_is_1(self) -> None:
        """Validate no retry when max attempts is 1."""
        transport = _StubSyncTransport(
            [_resp(503)],
            middlewares=[RetryMiddleware(RetryPolicy(max_attempts=1))],
        )
        resp = transport.send(_req())
        assert resp.status_code == 503
        assert transport.calls == 1

    def test_retries_on_retryable_status_code(self) -> None:
        """Validate retries on retryable status code."""
        policy = HttpRetryPolicy(
            max_attempts=3,
            backoff_initial=0.0,
            retryable_status_codes=frozenset({503}),
        )
        transport = _StubSyncTransport(
            [_resp(503), _resp(503), _resp(200)],
            middlewares=[RetryMiddleware(policy)],
        )
        resp = transport.send(_req())
        assert resp.status_code == 200
        assert transport.calls == 3

    def test_returns_last_retryable_response_when_exhausted(self) -> None:
        """Validate returns last retryable response when exhausted."""
        policy = HttpRetryPolicy(
            max_attempts=2,
            backoff_initial=0.0,
            retryable_status_codes=frozenset({503}),
        )
        transport = _StubSyncTransport(
            [_resp(503), _resp(503)],
            middlewares=[RetryMiddleware(policy)],
        )
        resp = transport.send(_req())
        assert resp.status_code == 503
        assert transport.calls == 2

    def test_retries_on_network_error(self) -> None:
        """Validate retries on network error."""
        policy = RetryPolicy(
            max_attempts=3,
            backoff_initial=0.0,
            retry_on_network_error=True,
        )
        transport = _ErrorSyncTransport(
            fail_times=2,
            success_response=_resp(200),
            middlewares=[RetryMiddleware(policy)],
        )
        resp = transport.send(_req())
        assert resp.status_code == 200
        assert transport.calls == 3

    def test_raises_network_error_when_disabled(self) -> None:
        """Validate raises network error when disabled."""
        policy = RetryPolicy(
            max_attempts=3,
            backoff_initial=0.0,
            retry_on_network_error=False,
        )
        transport = _ErrorSyncTransport(
            fail_times=1,
            success_response=_resp(200),
            exc=ConnectionError("boom"),
            middlewares=[RetryMiddleware(policy)],
        )
        with pytest.raises(ConnectionError, match="boom"):
            transport.send(_req())
        assert transport.calls == 1

    def test_raises_after_all_attempts_fail(self) -> None:
        """Validate raises after all attempts fail."""
        policy = RetryPolicy(
            max_attempts=2,
            backoff_initial=0.0,
            retry_on_network_error=True,
        )
        transport = _ErrorSyncTransport(
            fail_times=5,
            success_response=_resp(200),
            exc=ConnectionError("always fails"),
            middlewares=[RetryMiddleware(policy)],
        )
        with pytest.raises(ConnectionError, match="always fails"):
            transport.send(_req())
        assert transport.calls == 2

    def test_does_not_retry_non_network_exception_by_default(self) -> None:
        """Validate non-network exceptions are not retried by default."""
        policy = RetryPolicy(
            max_attempts=3,
            backoff_initial=0.0,
            retry_on_network_error=True,
        )
        transport = _ErrorSyncTransport(
            fail_times=3,
            success_response=_resp(200),
            exc=ValueError("not retryable"),
            middlewares=[RetryMiddleware(policy)],
        )
        with pytest.raises(ValueError, match="not retryable"):
            transport.send(_req())
        assert transport.calls == 1

    def test_retries_custom_exception_when_classifier_allows(self) -> None:
        """Validate custom classifier can mark extra exceptions retryable."""
        policy = RetryPolicy(
            max_attempts=3,
            backoff_initial=0.0,
            retry_on_network_error=True,
            retryable_exception_classifier=lambda exc: isinstance(exc, ValueError),
        )
        transport = _ErrorSyncTransport(
            fail_times=2,
            success_response=_resp(200),
            exc=ValueError("retryable by policy"),
            middlewares=[RetryMiddleware(policy)],
        )
        resp = transport.send(_req())
        assert resp.status_code == 200
        assert transport.calls == 3

    def test_non_retryable_status_code_stops_retries(self) -> None:
        """Validate non retryable status code stops retries."""
        policy = HttpRetryPolicy(
            max_attempts=3,
            backoff_initial=0.0,
            retryable_status_codes=frozenset({503}),
        )
        # 404 is NOT in retryable codes — should stop immediately.
        transport = _StubSyncTransport(
            [_resp(404)],
            middlewares=[RetryMiddleware(policy)],
        )
        resp = transport.send(_req())
        assert resp.status_code == 404
        assert transport.calls == 1


# ---------------------------------------------------------------------------
# BaseAsyncTransport — mirrors sync tests
# ---------------------------------------------------------------------------


class TestBaseAsyncTransportSend:
    """Test suite for BaseAsyncTransportSend."""

    async def test_delegates_to_send_once(self) -> None:
        """Validate delegates to send once."""
        transport = _StubAsyncTransport([_resp(200)])
        resp = await transport.send(_req())
        assert resp.status_code == 200
        assert transport.calls == 1

    async def test_is_abstract_without_send_once(self) -> None:
        """Validate is abstract without send once."""
        with pytest.raises(TypeError):
            BaseAsyncTransport()  # type: ignore  # pylint: disable=abstract-class-instantiated


class TestBaseAsyncTransportRetry:
    """Test suite for BaseAsyncTransportRetry."""

    async def test_no_retry_when_max_attempts_is_1(self) -> None:
        """Validate no retry when max attempts is 1."""
        transport = _StubAsyncTransport(
            [_resp(503)],
            middlewares=[AsyncRetryMiddleware(RetryPolicy(max_attempts=1))],
        )
        resp = await transport.send(_req())
        assert resp.status_code == 503
        assert transport.calls == 1

    async def test_retries_on_retryable_status_code(self) -> None:
        """Validate retries on retryable status code."""
        policy = HttpRetryPolicy(
            max_attempts=3,
            backoff_initial=0.0,
            retryable_status_codes=frozenset({503}),
        )
        transport = _StubAsyncTransport(
            [_resp(503), _resp(503), _resp(200)],
            middlewares=[AsyncRetryMiddleware(policy)],
        )
        resp = await transport.send(_req())
        assert resp.status_code == 200
        assert transport.calls == 3

    async def test_returns_last_retryable_response_when_exhausted(self) -> None:
        """Validate returns last retryable response when exhausted."""
        policy = HttpRetryPolicy(
            max_attempts=2,
            backoff_initial=0.0,
            retryable_status_codes=frozenset({503}),
        )
        transport = _StubAsyncTransport(
            [_resp(503), _resp(503)],
            middlewares=[AsyncRetryMiddleware(policy)],
        )
        resp = await transport.send(_req())
        assert resp.status_code == 503
        assert transport.calls == 2

    async def test_retries_on_network_error(self) -> None:
        """Validate retries on network error."""
        policy = RetryPolicy(
            max_attempts=3,
            backoff_initial=0.0,
            retry_on_network_error=True,
        )
        transport = _ErrorAsyncTransport(
            fail_times=2,
            success_response=_resp(200),
            middlewares=[AsyncRetryMiddleware(policy)],
        )
        resp = await transport.send(_req())
        assert resp.status_code == 200
        assert transport.calls == 3

    async def test_raises_after_all_attempts_fail(self) -> None:
        """Validate raises after all attempts fail."""
        policy = RetryPolicy(
            max_attempts=2,
            backoff_initial=0.0,
            retry_on_network_error=True,
        )
        transport = _ErrorAsyncTransport(
            fail_times=5,
            success_response=_resp(200),
            exc=ConnectionError("always fails"),
            middlewares=[AsyncRetryMiddleware(policy)],
        )
        with pytest.raises(ConnectionError, match="always fails"):
            await transport.send(_req())
        assert transport.calls == 2

    async def test_raises_network_error_when_disabled(self) -> None:
        """Validate raises network error when disabled."""
        policy = RetryPolicy(
            max_attempts=3,
            backoff_initial=0.0,
            retry_on_network_error=False,
        )
        transport = _ErrorAsyncTransport(
            fail_times=1,
            success_response=_resp(200),
            exc=ConnectionError("no retry"),
            middlewares=[AsyncRetryMiddleware(policy)],
        )
        with pytest.raises(ConnectionError, match="no retry"):
            await transport.send(_req())
        assert transport.calls == 1

    async def test_does_not_retry_non_network_exception_by_default(self) -> None:
        """Validate non-network exceptions are not retried by default."""
        policy = RetryPolicy(
            max_attempts=3,
            backoff_initial=0.0,
            retry_on_network_error=True,
        )
        transport = _ErrorAsyncTransport(
            fail_times=3,
            success_response=_resp(200),
            exc=ValueError("not retryable"),
            middlewares=[AsyncRetryMiddleware(policy)],
        )
        with pytest.raises(ValueError, match="not retryable"):
            await transport.send(_req())
        assert transport.calls == 1

    async def test_retries_custom_exception_when_classifier_allows(self) -> None:
        """Validate custom classifier can mark extra exceptions retryable."""
        policy = RetryPolicy(
            max_attempts=3,
            backoff_initial=0.0,
            retry_on_network_error=True,
            retryable_exception_classifier=lambda exc: isinstance(exc, ValueError),
        )
        transport = _ErrorAsyncTransport(
            fail_times=2,
            success_response=_resp(200),
            exc=ValueError("retryable by policy"),
            middlewares=[AsyncRetryMiddleware(policy)],
        )
        resp = await transport.send(_req())
        assert resp.status_code == 200
        assert transport.calls == 3


# ---------------------------------------------------------------------------
# Middleware wiring
# ---------------------------------------------------------------------------


class _RecordingSyncMiddleware:
    """Sync middleware that records requests and responses via handle()."""

    def __init__(self) -> None:
        """Initialize _RecordingSyncMiddleware."""
        self.requests: list[Request] = []
        self.responses: list[Response] = []

    def handle(
        self,
        request: Request,
        next_handler: Callable[[Request], Response],
    ) -> Response:
        """Return handle."""
        self.requests.append(request)
        response = next_handler(request)
        self.responses.append(response)
        return response


class _RecordingAsyncMiddleware:
    """Async middleware that records requests and responses via handle()."""

    def __init__(self) -> None:
        """Initialize _RecordingAsyncMiddleware."""
        self.requests: list[Request] = []
        self.responses: list[Response] = []

    async def handle(
        self,
        request: Request,
        next_handler: NextAsyncHandler,
    ) -> Response:
        """Return handle."""
        self.requests.append(request)
        response = await next_handler(request)
        self.responses.append(response)
        return response


class TestBaseSyncTransportMiddleware:
    """Tests that middleware is wired correctly in BaseSyncTransport."""

    def test_handle_called_with_request(self) -> None:
        """Validate handle called with request."""
        mw = _RecordingSyncMiddleware()
        transport = _StubSyncTransport([_resp(200)], middlewares=[mw])
        req = _req()
        transport.send(req)
        assert len(mw.requests) == 1
        assert mw.requests[0] is req

    def test_handle_receives_response(self) -> None:
        """Validate handle receives response."""
        expected = _resp(200)
        mw = _RecordingSyncMiddleware()
        transport = _StubSyncTransport([expected], middlewares=[mw])
        req = _req()
        response = transport.send(req)
        assert len(mw.responses) == 1
        assert mw.responses[0] is response

    def test_multiple_middlewares_called_in_onion_order(self) -> None:
        """First middleware is outermost — enters first, exits last."""
        order: list[str] = []

        class _First:
            """Represent First."""

            def handle(
                self, request: Request, next_handler: Callable[[Request], Response]
            ) -> Response:
                """Return handle."""
                order.append("first-enter")
                response = next_handler(request)
                order.append("first-exit")
                return response

        class _Second:
            """Represent Second."""

            def handle(
                self, request: Request, next_handler: Callable[[Request], Response]
            ) -> Response:
                """Return handle."""
                order.append("second-enter")
                response = next_handler(request)
                order.append("second-exit")
                return response

        transport = _StubSyncTransport([_resp(200)], middlewares=[_First(), _Second()])
        transport.send(_req())
        assert order == ["first-enter", "second-enter", "second-exit", "first-exit"]

    def test_no_middleware_by_default(self) -> None:
        """Validate no middleware by default."""
        transport = _StubSyncTransport([_resp(200)])
        assert transport._middlewares == []
        transport.send(_req())  # must not raise

    def test_middleware_can_short_circuit(self) -> None:
        """A middleware may return a response without calling next_handler."""
        short_circuit_response = _resp(200)

        class _ShortCircuit:
            """Represent ShortCircuit."""

            def handle(
                self, request: Request, next_handler: Callable[[Request], Response]
            ) -> Response:
                """Return handle."""
                return short_circuit_response

        transport = _StubSyncTransport([], middlewares=[_ShortCircuit()])
        response = transport.send(_req())
        assert response is short_circuit_response


class TestBaseAsyncTransportMiddleware:
    """Tests that middleware is wired correctly in BaseAsyncTransport."""

    async def test_handle_called_with_request(self) -> None:
        """Validate handle called with request."""
        mw = _RecordingAsyncMiddleware()
        transport = _StubAsyncTransport([_resp(200)], middlewares=[mw])
        req = _req()
        await transport.send(req)
        assert len(mw.requests) == 1
        assert mw.requests[0] is req

    async def test_handle_receives_response(self) -> None:
        """Validate handle receives response."""
        expected = _resp(200)
        mw = _RecordingAsyncMiddleware()
        transport = _StubAsyncTransport([expected], middlewares=[mw])
        req = _req()
        response = await transport.send(req)
        assert len(mw.responses) == 1
        assert mw.responses[0] is response

    async def test_multiple_middlewares_called_in_onion_order(self) -> None:
        """First middleware is outermost — enters first, exits last."""
        order: list[str] = []

        class _First:
            """Represent First."""

            async def handle(
                self, request: Request, next_handler: NextAsyncHandler
            ) -> Response:
                """Return handle."""
                order.append("first-enter")
                response = await next_handler(request)
                order.append("first-exit")
                return response

        class _Second:
            """Represent Second."""

            async def handle(
                self, request: Request, next_handler: NextAsyncHandler
            ) -> Response:
                """Return handle."""
                order.append("second-enter")
                response = await next_handler(request)
                order.append("second-exit")
                return response

        transport = _StubAsyncTransport([_resp(200)], middlewares=[_First(), _Second()])
        await transport.send(_req())
        assert order == ["first-enter", "second-enter", "second-exit", "first-exit"]

    async def test_no_middleware_by_default(self) -> None:
        """Validate no middleware by default."""
        transport = _StubAsyncTransport([_resp(200)])
        assert transport._middlewares == []
        await transport.send(_req())  # must not raise

    async def test_middleware_can_short_circuit(self) -> None:
        """A middleware may return a response without calling next_handler."""
        short_circuit_response = _resp(200)

        class _ShortCircuit:
            """Represent ShortCircuit."""

            async def handle(
                self, request: Request, next_handler: Callable[..., object]
            ) -> Response:
                """Return handle."""
                return short_circuit_response

        transport = _StubAsyncTransport([], middlewares=[_ShortCircuit()])
        response = await transport.send(_req())
        assert response is short_circuit_response
