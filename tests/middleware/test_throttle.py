"""Tests for throttle governance middleware."""

# pylint: disable=protected-access
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import cast

import pytest
import time_machine

from plynt.base.middleware import AsyncMiddleware, SyncMiddleware
from plynt.base.policies import (
    ThrottleGovernanceAction,
    ThrottleGovernancePolicy,
    ThrottleSignal,
)
from plynt.base.request import Request
from plynt.base.response import Response
from plynt.middleware.throttle import (
    AsyncThrottleGovernanceMiddleware,
    ThrottleGovernanceMiddleware,
    ThrottleGovernedError,
    _extract_throttle_signal,
    _parse_reset_at,
    _parse_retry_after,
)


def test_throttle_module_exports_error_class() -> None:
    """Throttle module __all__ includes the governed-error export."""
    import plynt.middleware.throttle as throttle_module

    assert "ThrottleGovernedError" in throttle_module.__all__


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

    def test_governance_action_is_str(self) -> None:
        """Test that action members are str instances (StrEnum)."""
        for action in ThrottleGovernanceAction:
            assert isinstance(action, str)


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

    def test_policy_validation_min_delay_nan(self) -> None:
        """Test that NaN min_delay raises ValueError."""
        with pytest.raises(ValueError, match="min_delay_seconds must be finite"):
            ThrottleGovernancePolicy(min_delay_seconds=float("nan"))

    def test_policy_validation_min_delay_inf(self) -> None:
        """Test that Infinity min_delay raises ValueError."""
        with pytest.raises(ValueError, match="min_delay_seconds must be finite"):
            ThrottleGovernancePolicy(min_delay_seconds=float("inf"))

    def test_policy_validation_max_delay_nan(self) -> None:
        """Test that NaN max_delay raises ValueError."""
        with pytest.raises(ValueError, match="max_delay_seconds must be finite"):
            ThrottleGovernancePolicy(max_delay_seconds=float("nan"))

    def test_policy_validation_max_delay_inf(self) -> None:
        """Test that Infinity max_delay raises ValueError."""
        with pytest.raises(ValueError, match="max_delay_seconds must be finite"):
            ThrottleGovernancePolicy(max_delay_seconds=float("inf"))

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

    def test_evaluate_uses_reset_at_when_retry_after_absent(self) -> None:
        """Test evaluate converts reset_at_seconds to delay when retry_after absent."""

        fixed_now = 1_000_000.0
        reset_at = fixed_now + 45.0
        policy = ThrottleGovernancePolicy(min_delay_seconds=1.0)
        signal = ThrottleSignal(detected=True, reset_at_seconds=reset_at)

        with time_machine.travel(fixed_now, tick=False):
            decision = policy.evaluate(signal)

        assert decision.action == ThrottleGovernanceAction.DELAY
        assert decision.delay_seconds == 45.0

    def test_evaluate_prefers_retry_after_over_reset_at(self) -> None:
        """Test that retry_after_seconds takes priority over reset_at_seconds."""

        fixed_now = 1_000_000.0
        policy = ThrottleGovernancePolicy(min_delay_seconds=1.0)
        signal = ThrottleSignal(
            detected=True,
            retry_after_seconds=10.0,
            reset_at_seconds=fixed_now + 60.0,
        )

        with time_machine.travel(fixed_now, tick=False):
            decision = policy.evaluate(signal)

        assert decision.delay_seconds == 10.0

    def test_evaluate_reset_at_past_clamps_to_min_delay(self) -> None:
        """Test reset_at in the past does not produce a negative delay."""

        fixed_now = 1_000_000.0
        policy = ThrottleGovernancePolicy(min_delay_seconds=2.0)
        signal = ThrottleSignal(detected=True, reset_at_seconds=fixed_now - 10.0)

        with time_machine.travel(fixed_now, tick=False):
            decision = policy.evaluate(signal)

        assert decision.delay_seconds == 2.0


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

        request = Request(method="GET", url="http://example.com/test")

        result = middleware.handle(request, lambda _req: response)
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

        request = Request(method="GET", url="http://example.com/test")

        result = middleware.handle(request, lambda _req: response)
        assert result.__dict__["_governance_delay_seconds"] == 3.0

    @pytest.mark.parametrize(
        ("fixed_now", "expected_delay"),
        [
            pytest.param(
                datetime(2026, 10, 21, 7, 27, 30, tzinfo=UTC), 30.0, id="future"
            ),
            pytest.param(
                datetime(2026, 10, 21, 7, 28, 0, tzinfo=UTC), 4.0, id="present"
            ),
            pytest.param(datetime(2026, 10, 21, 7, 28, 30, tzinfo=UTC), 4.0, id="past"),
        ],
    )
    def test_parses_retry_after_http_date(
        self, fixed_now: datetime, expected_delay: float
    ) -> None:
        """Verify HTTP-date delays and minimum clamping with a fixed clock"""
        policy = ThrottleGovernancePolicy(min_delay_seconds=4.0)
        middleware = ThrottleGovernanceMiddleware(policy=policy)

        response = Response(
            status_code=429,
            headers={"retry-after": "Wed, 21 Oct 2026 07:28:00 GMT"},
            content=b"Too Many Requests",
        )

        request = Request(method="GET", url="http://example.com/test")

        with time_machine.travel(fixed_now, tick=False):
            result = middleware.handle(request, lambda _req: response)

        assert result.__dict__["_governance_delay_seconds"] == expected_delay


class TestThrottleGovernanceMiddleware:
    """Tests for sync ThrottleGovernanceMiddleware."""

    def test_middleware_initialization(self) -> None:
        """Test middleware initialization with default policy."""
        middleware = ThrottleGovernanceMiddleware()
        assert middleware._policy is not None
        assert middleware._policy.reject_on_detection is False

    def test_middleware_satisfies_protocol(self) -> None:
        """Test that middleware satisfies SyncMiddleware protocol."""
        assert isinstance(ThrottleGovernanceMiddleware(), SyncMiddleware)

    def test_middleware_with_custom_policy(self) -> None:
        """Test middleware initialization with custom policy."""
        policy = ThrottleGovernancePolicy(reject_on_detection=True)
        middleware = ThrottleGovernanceMiddleware(policy=policy)
        assert middleware._policy is policy

    def test_middleware_passes_through_200(self) -> None:
        """Test that 200 responses pass through unchanged."""
        policy = ThrottleGovernancePolicy()
        middleware = ThrottleGovernanceMiddleware(policy=policy)

        response = Response(status_code=200, headers={}, content=b"OK")

        def next_handler(_req: Request) -> Response:
            return response

        request = Request(method="GET", url="http://example.com/test")

        result = middleware.handle(request, next_handler)
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

        request = Request(method="GET", url="http://example.com/test")

        result = middleware.handle(request, next_handler)
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

        request = Request(method="GET", url="http://example.com/test")

        with pytest.raises(ThrottleGovernedError) as exc_info:
            middleware.handle(request, next_handler)

        error = exc_info.value
        assert error.response is response
        assert error.delay_seconds == 0.0


class TestAsyncThrottleGovernanceMiddleware:
    """Tests for async ThrottleGovernanceMiddleware."""

    @pytest.mark.asyncio
    async def test_async_middleware_initialization(self) -> None:
        """Test async middleware initialization with default policy."""
        middleware = AsyncThrottleGovernanceMiddleware()
        assert middleware._policy is not None
        assert middleware._policy.reject_on_detection is False

    @pytest.mark.asyncio
    async def test_async_middleware_satisfies_protocol(self) -> None:
        """Test that async middleware satisfies AsyncMiddleware protocol."""
        assert isinstance(AsyncThrottleGovernanceMiddleware(), AsyncMiddleware)

    @pytest.mark.asyncio
    async def test_async_middleware_passes_through_200(self) -> None:
        """Test that 200 responses pass through unchanged."""
        policy = ThrottleGovernancePolicy()
        middleware = AsyncThrottleGovernanceMiddleware(policy=policy)

        response = Response(status_code=200, headers={}, content=b"OK")

        async def next_handler(_req: Request) -> Response:
            return response

        request = Request(method="GET", url="http://example.com/test")

        result = await middleware.handle(request, next_handler)
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

        request = Request(method="GET", url="http://example.com/test")

        result = await middleware.handle(request, next_handler)
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

        request = Request(method="GET", url="http://example.com/test")

        with pytest.raises(ThrottleGovernedError) as exc_info:
            await middleware.handle(request, next_handler)

        error = exc_info.value
        assert error.response is response
        assert error.delay_seconds == 0.0

    @pytest.mark.asyncio
    async def test_async_middleware_raises_type_error_for_non_response(self) -> None:
        """Test that async middleware rejects non-Response handler results."""
        middleware = AsyncThrottleGovernanceMiddleware()

        async def next_handler(_req: Request) -> Response:
            return cast(Response, object())

        request = Request(method="GET", url="http://example.com/test")

        with pytest.raises(TypeError, match="next_handler must return Response"):
            await middleware.handle(request, next_handler)


class TestParseRetryAfter:
    """Tests for _parse_retry_after header parser."""

    def test_parse_retry_after_seconds_integer(self) -> None:
        """Test parsing Retry-After with integer seconds."""
        response = Response(status_code=429, headers={"retry-after": "60"})
        assert _parse_retry_after(response) == 60.0

    def test_parse_retry_after_seconds_decimal(self) -> None:
        """Test parsing Retry-After with decimal seconds."""
        response = Response(status_code=429, headers={"retry-after": "30.5"})
        assert _parse_retry_after(response) == 30.5

    def test_parse_retry_after_missing(self) -> None:
        """Test parsing when Retry-After header is missing."""
        response = Response(status_code=429, headers={})
        assert _parse_retry_after(response) is None

    def test_parse_retry_after_case_insensitive(self) -> None:
        """Test parsing with case-insensitive header lookup."""
        response = Response(status_code=429, headers={"Retry-After": "45"})
        assert _parse_retry_after(response) == 45.0

    def test_parse_retry_after_http_date_future(self) -> None:
        """Test parsing Retry-After with future HTTP-date."""
        fixed_now = datetime(2026, 5, 16, 12, 0, 0, tzinfo=UTC)
        fixed_future = fixed_now + timedelta(seconds=30)
        date_str = fixed_future.strftime("%a, %d %b %Y %H:%M:%S GMT")

        response = Response(status_code=429, headers={"retry-after": date_str})
        with time_machine.travel(fixed_now, tick=False):
            result = _parse_retry_after(response)

        assert result == 30.0

    def test_parse_retry_after_http_date_past(self) -> None:
        """Test parsing Retry-After with past HTTP-date returns 0."""
        fixed_now = datetime(2026, 5, 16, 12, 0, 0, tzinfo=UTC)
        past = fixed_now - timedelta(seconds=30)
        date_str = past.strftime("%a, %d %b %Y %H:%M:%S GMT")

        response = Response(status_code=429, headers={"retry-after": date_str})
        with time_machine.travel(fixed_now, tick=False):
            result = _parse_retry_after(response)

        assert result == 0.0

    def test_parse_retry_after_invalid_format(self) -> None:
        """Test parsing with invalid format returns None."""
        response = Response(status_code=429, headers={"retry-after": "not-a-number"})
        assert _parse_retry_after(response) is None

    def test_parse_retry_after_nan_returns_none(self) -> None:
        """Test that NaN is rejected as non-finite."""
        response = Response(status_code=429, headers={"retry-after": "NaN"})
        assert _parse_retry_after(response) is None

    def test_parse_retry_after_inf_returns_none(self) -> None:
        """Test that Infinity is rejected as non-finite."""
        response = Response(status_code=429, headers={"retry-after": "inf"})
        assert _parse_retry_after(response) is None

    def test_parse_retry_after_negative_inf_returns_none(self) -> None:
        """Test that negative Infinity is rejected as non-finite."""
        response = Response(status_code=429, headers={"retry-after": "-inf"})
        assert _parse_retry_after(response) is None


class TestParseResetAt:
    """Tests for _parse_reset_at helper."""

    def test_parse_reset_at_integer(self) -> None:
        """Test parsing X-RateLimit-Reset as a Unix timestamp."""
        response = Response(
            status_code=429, headers={"x-ratelimit-reset": "1748000000"}
        )
        assert _parse_reset_at(response) == 1_748_000_000.0

    def test_parse_reset_at_missing(self) -> None:
        """Test that missing header returns None."""
        response = Response(status_code=429, headers={})
        assert _parse_reset_at(response) is None

    def test_parse_reset_at_case_insensitive(self) -> None:
        """Test case-insensitive header lookup."""
        response = Response(
            status_code=429, headers={"X-RateLimit-Reset": "1748000000"}
        )
        assert _parse_reset_at(response) == 1_748_000_000.0

    def test_parse_reset_at_invalid_returns_none(self) -> None:
        """Test that non-numeric value returns None."""
        response = Response(
            status_code=429, headers={"x-ratelimit-reset": "not-a-timestamp"}
        )
        assert _parse_reset_at(response) is None


class TestExtractThrottleSignalResetAt:
    """Tests for _extract_throttle_signal populating reset_at_seconds."""

    def test_quota_exhausted_extracts_reset_at(self) -> None:
        """Test that X-RateLimit-Reset is captured alongside quota exhaustion."""
        response = Response(
            status_code=200,
            headers={
                "x-ratelimit-remaining": "0",
                "x-ratelimit-reset": "1748000000",
            },
            content=b"ok",
        )
        signal = _extract_throttle_signal(response)
        assert signal.detected is True
        assert signal.reset_at_seconds == 1_748_000_000.0

    def test_quota_exhausted_no_reset_at_when_header_absent(self) -> None:
        """Test reset_at_seconds is None when X-RateLimit-Reset is absent."""
        response = Response(
            status_code=200,
            headers={"x-ratelimit-remaining": "0"},
            content=b"ok",
        )
        signal = _extract_throttle_signal(response)
        assert signal.detected is True
        assert signal.reset_at_seconds is None

    def test_429_with_ratelimit_reset_extracts_reset_at(self) -> None:
        """Test that X-RateLimit-Reset is captured on a 429 response."""
        response = Response(
            status_code=429,
            headers={"x-ratelimit-reset": "1748000000"},
            content=b"",
        )
        signal = _extract_throttle_signal(response)
        assert signal.detected is True
        assert signal.reset_at_seconds == 1_748_000_000.0

    def test_429_without_ratelimit_reset_has_none(self) -> None:
        """Test reset_at_seconds is None when X-RateLimit-Reset is absent on 429."""
        response = Response(status_code=429, headers={}, content=b"")
        signal = _extract_throttle_signal(response)
        assert signal.detected is True
        assert signal.reset_at_seconds is None

    def test_503_with_retry_after_and_ratelimit_reset(self) -> None:
        """Test that X-RateLimit-Reset is captured on a throttling 503 response."""
        response = Response(
            status_code=503,
            headers={"retry-after": "30", "x-ratelimit-reset": "1748000000"},
            content=b"",
        )
        signal = _extract_throttle_signal(response)
        assert signal.detected is True
        assert signal.reset_at_seconds == 1_748_000_000.0
