"""Tests for throttle governance middleware."""

from __future__ import annotations

from typing import cast

import pytest

from plynth.base.policies import (
    ThrottleGovernanceAction,
    ThrottleGovernancePolicy,
    ThrottleSignal,
)
from plynth.base.request import Request
from plynth.base.response import Response
from plynth.middleware.throttle import (
    AsyncThrottleGovernanceMiddleware,
    ThrottleGovernanceMiddleware,
    ThrottleGovernedError,
)


class TestThrottleSignal:
    """Tests for ThrottleSignal model."""

    def test_throttle_signal_detected(self) -> None:
        """Test creating a detected throttle signal."""
        signal = ThrottleSignal(
            detected=True,
            retry_after_seconds=30.0,
        )
        assert signal.detected is True
        assert signal.retry_after_seconds == 30.0

    def test_throttle_signal_not_detected(self) -> None:
        """Test creating an undetected throttle signal."""
        signal = ThrottleSignal(detected=False)
        assert signal.detected is False
        assert signal.retry_after_seconds is None


class TestThrottleGovernanceAction:
    """Tests for ThrottleGovernanceAction enum."""

    def test_governance_action_values(self) -> None:
        """Test governance action enum values."""
        assert ThrottleGovernanceAction.PROCEED.value == "proceed"
        assert ThrottleGovernanceAction.DELAY.value == "delay"
        assert ThrottleGovernanceAction.REJECT.value == "reject"


class TestThrottleGovernancePolicy:
    """Tests for ThrottleGovernancePolicy."""

    def test_policy_defaults(self) -> None:
        """Test policy default values."""
        policy = ThrottleGovernancePolicy()
        assert policy.reject_on_detection is False
        assert policy.min_delay_seconds == 0.5
        assert policy.max_delay_seconds == 60.0

    def test_policy_validation_negative_min_delay(self) -> None:
        """Test that negative min_delay raises ValueError."""
        with pytest.raises(ValueError, match="min_delay_seconds must be >= 0"):
            ThrottleGovernancePolicy(min_delay_seconds=-1.0)

    def test_policy_validation_max_less_than_min(self) -> None:
        """Test that max < min raises ValueError."""
        with pytest.raises(
            ValueError, match="max_delay_seconds must be >= min_delay_seconds"
        ):
            ThrottleGovernancePolicy(min_delay_seconds=60.0, max_delay_seconds=30.0)

    def test_evaluate_no_throttle(self) -> None:
        """Test evaluate with no throttle detected."""
        policy = ThrottleGovernancePolicy()
        signal = ThrottleSignal(detected=False)
        decision = policy.evaluate(signal)

        assert decision.action == ThrottleGovernanceAction.PROCEED
        assert decision.delay_seconds == 0.0
        assert "No throttle detected" in decision.reason

    def test_evaluate_throttle_with_reject_on_detection(self) -> None:
        """Test evaluate with throttle and reject_on_detection=True."""
        policy = ThrottleGovernancePolicy(reject_on_detection=True)
        signal = ThrottleSignal(detected=True, retry_after_seconds=30.0)
        decision = policy.evaluate(signal)

        assert decision.action == ThrottleGovernanceAction.REJECT
        assert decision.delay_seconds == 0.0

    def test_evaluate_throttle_with_delay(self) -> None:
        """Test evaluate with throttle and delay action."""
        policy = ThrottleGovernancePolicy(
            reject_on_detection=False,
            min_delay_seconds=1.0,
            max_delay_seconds=60.0,
        )
        signal = ThrottleSignal(detected=True, retry_after_seconds=30.0)
        decision = policy.evaluate(signal)

        assert decision.action == ThrottleGovernanceAction.DELAY
        assert decision.delay_seconds == 30.0

    def test_evaluate_throttle_delay_clamped_to_min(self) -> None:
        """Test that delay is clamped to min_delay_seconds."""
        policy = ThrottleGovernancePolicy(
            reject_on_detection=False,
            min_delay_seconds=5.0,
            max_delay_seconds=60.0,
        )
        signal = ThrottleSignal(detected=True, retry_after_seconds=2.0)
        decision = policy.evaluate(signal)

        assert decision.action == ThrottleGovernanceAction.DELAY
        assert decision.delay_seconds == 5.0

    def test_evaluate_throttle_delay_clamped_to_max(self) -> None:
        """Test that delay is clamped to max_delay_seconds."""
        policy = ThrottleGovernancePolicy(
            reject_on_detection=False,
            min_delay_seconds=1.0,
            max_delay_seconds=30.0,
        )
        signal = ThrottleSignal(detected=True, retry_after_seconds=120.0)
        decision = policy.evaluate(signal)

        assert decision.action == ThrottleGovernanceAction.DELAY
        assert decision.delay_seconds == 30.0


class TestThrottleGovernedError:
    """Tests for ThrottleGovernedError exception."""

    def test_error_initialization(self) -> None:
        """Test initializing throttle governed error."""
        response = Response(status_code=429, headers={}, content=b"")
        error = ThrottleGovernedError(
            response=response,
            delay_seconds=30.0,
            reason="Throttled by server",
        )

        assert error.response is response
        assert error.delay_seconds == 30.0
        assert error.reason == "Throttled by server"
        assert "rejected" in str(error).lower()


class TestThrottleSignalExtraction:
    """Tests for throttle signal extraction helper paths."""

    def test_detects_503_with_retry_after(self) -> None:
        """Test that 503 + Retry-After is treated as throttle."""
        policy = ThrottleGovernancePolicy(min_delay_seconds=1.0)
        middleware = ThrottleGovernanceMiddleware(policy=policy)

        response = Response(
            status_code=503,
            headers={"retry-after": "5"},
            content=b"Service Unavailable",
        )

        middleware.next_handler = lambda _req: response
        request = Request(method="GET", url="http://example.com/test")

        result = middleware(request)
        assert result.__dict__["_governance_delay_seconds"] == 5.0

    def test_detects_quota_exhaustion_header(self) -> None:
        """Test that exhausted quota header triggers throttle detection."""
        policy = ThrottleGovernancePolicy(min_delay_seconds=3.0)
        middleware = ThrottleGovernanceMiddleware(policy=policy)

        response = Response(
            status_code=200,
            headers={"x-ratelimit-remaining": "0"},
            content=b"OK",
        )

        middleware.next_handler = lambda _req: response
        request = Request(method="GET", url="http://example.com/test")

        result = middleware(request)
        assert result.__dict__["_governance_delay_seconds"] == 3.0

    def test_ignores_invalid_retry_after_date_format(self) -> None:
        """Test that invalid Retry-After format falls back to min delay."""
        policy = ThrottleGovernancePolicy(min_delay_seconds=4.0)
        middleware = ThrottleGovernanceMiddleware(policy=policy)

        response = Response(
            status_code=429,
            headers={"retry-after": "Wed, 21 Oct 2026 07:28:00 GMT"},
            content=b"Too Many Requests",
        )

        middleware.next_handler = lambda _req: response
        request = Request(method="GET", url="http://example.com/test")

        result = middleware(request)
        assert result.__dict__["_governance_delay_seconds"] == 4.0


class TestThrottleGovernanceMiddleware:
    """Tests for sync ThrottleGovernanceMiddleware."""

    def test_middleware_initialization(self) -> None:
        """Test middleware initialization with default policy."""
        middleware = ThrottleGovernanceMiddleware()
        assert middleware.policy is not None
        assert middleware.policy.reject_on_detection is False

    def test_middleware_with_custom_policy(self) -> None:
        """Test middleware initialization with custom policy."""
        policy = ThrottleGovernancePolicy(reject_on_detection=True)
        middleware = ThrottleGovernanceMiddleware(policy=policy)
        assert middleware.policy is policy

    def test_middleware_no_next_handler_raises(self) -> None:
        """Test that middleware without next_handler raises."""
        middleware = ThrottleGovernanceMiddleware()
        request = Request(method="GET", url="http://example.com/test")

        with pytest.raises(RuntimeError, match="next_handler not set"):
            middleware(request)

    def test_middleware_passes_through_200(self) -> None:
        """Test that 200 responses pass through unchanged."""
        policy = ThrottleGovernancePolicy()
        middleware = ThrottleGovernanceMiddleware(policy=policy)

        response = Response(status_code=200, headers={}, content=b"OK")

        def next_handler(_req: Request) -> Response:
            return response

        middleware.next_handler = next_handler
        request = Request(method="GET", url="http://example.com/test")

        result = middleware(request)
        assert result is response
        assert not hasattr(result, "_governance_delay_seconds")

    def test_middleware_detects_429(self) -> None:
        """Test that 429 is detected and governance delay attached."""
        policy = ThrottleGovernancePolicy(
            reject_on_detection=False,
            min_delay_seconds=2.0,
        )
        middleware = ThrottleGovernanceMiddleware(policy=policy)

        response = Response(
            status_code=429,
            headers={"retry-after": "30"},
            content=b"Too Many Requests",
        )

        def next_handler(_req: Request) -> Response:
            return response

        middleware.next_handler = next_handler
        request = Request(method="GET", url="http://example.com/test")

        result = middleware(request)
        assert result is response
        assert hasattr(result, "_governance_delay_seconds")
        assert result.__dict__["_governance_delay_seconds"] == 30.0

    def test_middleware_rejects_on_governance_reject(self) -> None:
        """Test that middleware raises when governance rejects."""
        policy = ThrottleGovernancePolicy(reject_on_detection=True)
        middleware = ThrottleGovernanceMiddleware(policy=policy)

        response = Response(
            status_code=429,
            headers={},
            content=b"Too Many Requests",
        )

        def next_handler(_req: Request) -> Response:
            return response

        middleware.next_handler = next_handler
        request = Request(method="GET", url="http://example.com/test")

        with pytest.raises(ThrottleGovernedError) as exc_info:
            middleware(request)

        error = exc_info.value
        assert error.response is response
        assert error.delay_seconds == 0.0


class TestAsyncThrottleGovernanceMiddleware:
    """Tests for async ThrottleGovernanceMiddleware."""

    @pytest.mark.asyncio
    async def test_async_middleware_initialization(self) -> None:
        """Test async middleware initialization with default policy."""
        middleware = AsyncThrottleGovernanceMiddleware()
        assert middleware.policy is not None
        assert middleware.policy.reject_on_detection is False

    @pytest.mark.asyncio
    async def test_async_middleware_no_next_handler_raises(self) -> None:
        """Test that async middleware without next_handler raises."""
        middleware = AsyncThrottleGovernanceMiddleware()
        request = Request(method="GET", url="http://example.com/test")

        with pytest.raises(RuntimeError, match="next_handler not set"):
            await middleware(request)

    @pytest.mark.asyncio
    async def test_async_middleware_passes_through_200(self) -> None:
        """Test that 200 responses pass through unchanged."""
        policy = ThrottleGovernancePolicy()
        middleware = AsyncThrottleGovernanceMiddleware(policy=policy)

        response = Response(status_code=200, headers={}, content=b"OK")

        async def next_handler(_req: Request) -> Response:
            return response

        middleware.next_handler = next_handler
        request = Request(method="GET", url="http://example.com/test")

        result = await middleware(request)
        assert result is response
        assert not hasattr(result, "_governance_delay_seconds")

    @pytest.mark.asyncio
    async def test_async_middleware_detects_429(self) -> None:
        """Test that async middleware detects 429 and attaches delay."""
        policy = ThrottleGovernancePolicy(
            reject_on_detection=False,
            min_delay_seconds=2.0,
        )
        middleware = AsyncThrottleGovernanceMiddleware(policy=policy)

        response = Response(
            status_code=429,
            headers={"retry-after": "30"},
            content=b"Too Many Requests",
        )

        async def next_handler(_req: Request) -> Response:
            return response

        middleware.next_handler = next_handler
        request = Request(method="GET", url="http://example.com/test")

        result = await middleware(request)
        assert result is response
        assert hasattr(result, "_governance_delay_seconds")
        assert result.__dict__["_governance_delay_seconds"] == 30.0

    @pytest.mark.asyncio
    async def test_async_middleware_rejects_on_governance_reject(self) -> None:
        """Test that async middleware raises when governance rejects."""
        policy = ThrottleGovernancePolicy(reject_on_detection=True)
        middleware = AsyncThrottleGovernanceMiddleware(policy=policy)

        response = Response(
            status_code=429,
            headers={},
            content=b"Too Many Requests",
        )

        async def next_handler(_req: Request) -> Response:
            return response

        middleware.next_handler = next_handler
        request = Request(method="GET", url="http://example.com/test")

        with pytest.raises(ThrottleGovernedError) as exc_info:
            await middleware(request)

        error = exc_info.value
        assert error.response is response
        assert error.delay_seconds == 0.0

    @pytest.mark.asyncio
    async def test_async_middleware_raises_type_error_for_non_response(self) -> None:
        """Test that async middleware rejects non-Response handler results."""
        middleware = AsyncThrottleGovernanceMiddleware()

        async def next_handler(_req: Request) -> Response:
            return cast(Response, object())

        middleware.next_handler = next_handler
        request = Request(method="GET", url="http://example.com/test")

        with pytest.raises(TypeError, match="next_handler must return Response"):
            await middleware(request)
