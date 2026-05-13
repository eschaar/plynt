"""Tests for plynth.middleware.retry (RetryMiddleware, AsyncRetryMiddleware).

Behaviour coverage (backoff, retryable status codes, network errors) is
provided by the transport integration tests in tests/base/test_transport.py.
These unit tests verify protocol satisfaction and the immediate-passthrough
path when ``max_attempts <= 1``.
"""

from __future__ import annotations

import pytest

from plynth.base.middleware import AsyncMiddleware, SyncMiddleware
from plynth.base.policies import RetryPolicy
from plynth.base.request import Request
from plynth.base.response import Response
from plynth.middleware.retry import AsyncRetryMiddleware, RetryMiddleware

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_REQUEST = Request(method="GET", url="https://example.com/api/resource")
_RESPONSE = Response(status_code=200, content=b"ok")

_POLICY_NO_RETRY = RetryPolicy(max_attempts=1)


def _noop(request: Request) -> Response:
    """Handle noop."""
    return _RESPONSE


async def _async_noop(request: Request) -> Response:
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
        result = mw.handle(_REQUEST, lambda r: expected)
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

        async def handler(req: Request) -> Response:
            """Return handler."""
            return expected

        mw = AsyncRetryMiddleware(_POLICY_NO_RETRY)
        result = await mw.handle(_REQUEST, handler)
        assert result is expected

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
