"""Tests for plynth.middleware.retry (RetryMiddleware, AsyncRetryMiddleware).

Behaviour coverage (backoff, retryable status codes, network errors) is
provided by the transport integration tests in tests/base/test_transport.py.
These unit tests verify protocol satisfaction and the immediate-passthrough
path when ``max_attempts <= 1``.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from plynth.base.middleware import AsyncMiddleware, SyncMiddleware
from plynth.base.policies import RetryPolicy
from plynth.base.request import Request
from plynth.base.response import Response
from plynth.middleware.retry import AsyncRetryMiddleware, RetryMiddleware
from plynth.middleware.throttle import ThrottleGovernedError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_REQUEST = Request(method="GET", url="https://example.com/api/resource")
_RESPONSE = Response(status_code=200, content=b"ok")

_POLICY_NO_RETRY = RetryPolicy(max_attempts=1)


def _noop(_request: Request) -> Response:
    """Handle noop."""
    return _RESPONSE


async def _async_noop(_request: Request) -> Response:
    """Handle async noop."""
    return _RESPONSE


# ---------------------------------------------------------------------------
# TestRetryMiddleware
# ---------------------------------------------------------------------------


class TestRetryMiddleware:
    """Tests for the synchronous RetryMiddleware."""

    def test_satisfies_sync_middleware_protocol(self) -> None:
        """Validate satisfies sync middleware protocol."""
        assert isinstance(RetryMiddleware(_POLICY_NO_RETRY), SyncMiddleware)

    def test_handle_calls_next_handler_once_when_no_retry(self) -> None:
        """Validate handle calls next handler once when no retry."""
        calls: list[Request] = []

        def handler(req: Request) -> Response:
            """Return handler."""
            calls.append(req)
            return _RESPONSE

        RetryMiddleware(_POLICY_NO_RETRY).handle(_REQUEST, handler)
        assert len(calls) == 1

    def test_handle_returns_response_from_next(self) -> None:
        """Validate handle returns response from next."""
        expected = Response(status_code=201, content=b"created")
        mw = RetryMiddleware(_POLICY_NO_RETRY)
        result = mw.handle(_REQUEST, lambda _req: expected)
        assert result is expected

    def test_handle_propagates_request_unchanged(self) -> None:
        """Validate handle propagates request unchanged."""
        captured: list[Request] = []

        def handler(req: Request) -> Response:
            """Return handler."""
            captured.append(req)
            return _RESPONSE

        RetryMiddleware(_POLICY_NO_RETRY).handle(_REQUEST, handler)
        assert captured[0] is _REQUEST


# ---------------------------------------------------------------------------
# TestAsyncRetryMiddleware
# ---------------------------------------------------------------------------


class TestAsyncRetryMiddleware:
    """Tests for the asynchronous AsyncRetryMiddleware."""

    def test_satisfies_async_middleware_protocol(self) -> None:
        """Validate satisfies async middleware protocol."""
        assert isinstance(AsyncRetryMiddleware(_POLICY_NO_RETRY), AsyncMiddleware)

    @pytest.mark.asyncio
    async def test_handle_calls_next_handler_once_when_no_retry(self) -> None:
        """Validate handle calls next handler once when no retry."""
        calls: list[Request] = []

        async def handler(req: Request) -> Response:
            """Return handler."""
            calls.append(req)
            return _RESPONSE

        await AsyncRetryMiddleware(_POLICY_NO_RETRY).handle(_REQUEST, handler)
        assert len(calls) == 1

    @pytest.mark.asyncio
    async def test_handle_returns_response_from_next(self) -> None:
        """Validate handle returns response from next."""
        expected = Response(status_code=201, content=b"created")

        async def handler(_req: Request) -> Response:
            """Return handler."""
            return expected

        mw = AsyncRetryMiddleware(_POLICY_NO_RETRY)
        result = await mw.handle(_REQUEST, handler)
        assert result is expected


# ---------------------------------------------------------------------------
# Governance Integration Tests
# ---------------------------------------------------------------------------


class TestRetryMiddlewareGovernanceIntegration:
    """Tests for retry middleware integration with throttle governance."""

    def test_retry_respects_governance_delay(self) -> None:
        """Validate retry uses governance delay over backoff."""

        calls: list[Request] = []

        def handler(req: Request) -> Response:
            """Handler that returns throttled response."""
            calls.append(req)

            # First call: return retryable 503 with governance delay
            if len(calls) == 1:
                resp = Response(
                    status_code=503,
                    headers={"retry-after": "2"},
                    content=b"Service Unavailable",
                )
                # Simulate governance delay attachment
                resp.__dict__["_governance_delay_seconds"] = 2.0
                resp.__dict__["_governance_reason"] = "Throttled; delaying 2.0s"
                return resp

            # Second call: success
            return Response(status_code=200, content=b"ok")

        policy = RetryPolicy(
            max_attempts=2,
            backoff_initial=0.1,
            retryable_status_codes=frozenset([503]),
        )
        mw = RetryMiddleware(policy)
        with patch("plynth.middleware.retry.time.sleep") as mock_sleep:
            result = mw.handle(_REQUEST, handler)

        assert result.status_code == 200
        assert len(calls) == 2
        # Governance delay (2.0s) should take precedence over backoff (0.1s)
        mock_sleep.assert_called_once_with(2.0)

    def test_retry_uses_backoff_when_no_governance_delay(self) -> None:
        """Validate retry uses backoff when governance delay absent."""

        calls: list[Request] = []

        def handler(req: Request) -> Response:
            """Handler without governance delay."""
            calls.append(req)

            if len(calls) == 1:
                return Response(
                    status_code=503,
                    headers={},
                    content=b"Service Unavailable",
                )

            return Response(status_code=200, content=b"ok")

        # Backoff for attempt 2 is 0.5s (backoff_initial * 1)
        policy = RetryPolicy(
            max_attempts=2,
            backoff_initial=0.5,
            retryable_status_codes=frozenset([503]),
        )
        mw = RetryMiddleware(policy)
        with patch("plynth.middleware.retry.time.sleep") as mock_sleep:
            result = mw.handle(_REQUEST, handler)

        assert result.status_code == 200
        assert len(calls) == 2
        mock_sleep.assert_called_once_with(0.5)

    def test_retry_uses_max_of_backoff_and_governance(self) -> None:
        """Validate retry uses max(backoff, governance_delay)."""

        calls: list[Request] = []

        def handler(req: Request) -> Response:
            """Handler with short governance delay but longer backoff."""
            calls.append(req)

            if len(calls) == 1:
                resp = Response(
                    status_code=503,
                    headers={},
                    content=b"Service Unavailable",
                )
                # Governance delay is short; backoff (0.5s) should win
                resp.__dict__["_governance_delay_seconds"] = 0.2
                return resp

            return Response(status_code=200, content=b"ok")

        # Backoff for attempt 2 is 0.5s (backoff_initial * 1)
        policy = RetryPolicy(
            max_attempts=2,
            backoff_initial=0.5,
            retryable_status_codes=frozenset([503]),
        )
        mw = RetryMiddleware(policy)
        with patch("plynth.middleware.retry.time.sleep") as mock_sleep:
            result = mw.handle(_REQUEST, handler)

        assert result.status_code == 200
        assert len(calls) == 2
        # max(0.5, 0.2) = 0.5
        mock_sleep.assert_called_once_with(0.5)

    def test_governance_reject_is_not_retried(self) -> None:
        """Test ThrottleGovernedError propagates immediately without retry."""
        calls: list[int] = []
        reject_response = Response(status_code=429, headers={}, content=b"")
        error = ThrottleGovernedError(
            response=reject_response, delay_seconds=0.0, reason="Rejected"
        )

        def handler(_req: Request) -> Response:
            """Always raise governance rejection."""
            calls.append(1)
            raise error

        policy = RetryPolicy(
            max_attempts=3,
            retry_on_network_error=True,
            retryable_exception_classifier=lambda _exc: True,
        )
        mw = RetryMiddleware(policy)
        with pytest.raises(ThrottleGovernedError):
            mw.handle(_REQUEST, handler)

        assert len(calls) == 1

    """Tests for async retry middleware integration with throttle governance."""

    @pytest.mark.asyncio
    async def test_async_retry_respects_governance_delay(self) -> None:
        """Validate async retry uses governance delay over backoff."""

        calls: list[Request] = []

        async def handler(req: Request) -> Response:
            """Handler that returns throttled response."""
            calls.append(req)

            if len(calls) == 1:
                resp = Response(
                    status_code=503,
                    headers={"retry-after": "2"},
                    content=b"Service Unavailable",
                )
                resp.__dict__["_governance_delay_seconds"] = 2.0
                resp.__dict__["_governance_reason"] = "Throttled; delaying 2.0s"
                return resp

            return Response(status_code=200, content=b"ok")

        policy = RetryPolicy(
            max_attempts=2,
            backoff_initial=0.1,
            retryable_status_codes=frozenset([503]),
        )
        mw = AsyncRetryMiddleware(policy)
        with patch(
            "plynth.middleware.retry.asyncio.sleep", new_callable=AsyncMock
        ) as mock_sleep:
            result = await mw.handle(_REQUEST, handler)

        assert result.status_code == 200
        assert len(calls) == 2
        mock_sleep.assert_called_once_with(2.0)

    @pytest.mark.asyncio
    async def test_handle_propagates_request_unchanged(self) -> None:
        """Validate handle propagates request unchanged."""
        captured: list[Request] = []

        async def handler(req: Request) -> Response:
            """Return handler."""
            captured.append(req)
            return _RESPONSE

        await AsyncRetryMiddleware(_POLICY_NO_RETRY).handle(_REQUEST, handler)
        assert captured[0] is _REQUEST

    @pytest.mark.asyncio
    async def test_async_governance_reject_is_not_retried(self) -> None:
        """Test ThrottleGovernedError propagates immediately without retry."""
        calls: list[int] = []
        reject_response = Response(status_code=429, headers={}, content=b"")
        error = ThrottleGovernedError(
            response=reject_response, delay_seconds=0.0, reason="Rejected"
        )

        async def handler(_req: Request) -> Response:
            """Always raise governance rejection."""
            calls.append(1)
            raise error

        policy = RetryPolicy(
            max_attempts=3,
            retry_on_network_error=True,
            retryable_exception_classifier=lambda _exc: True,
        )
        mw = AsyncRetryMiddleware(policy)
        with pytest.raises(ThrottleGovernedError):
            await mw.handle(_REQUEST, handler)

        assert len(calls) == 1
