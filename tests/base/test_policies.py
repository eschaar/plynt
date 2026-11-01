"""Tests for plynt.base.policies.CircuitBreakerPolicy and RateLimitPolicy."""

from __future__ import annotations

from typing import Any

import pytest

from plynt.base.policies import CircuitBreakerPolicy, RateLimitPolicy, RetryPolicy
from plynt.http.policies import HttpRetryPolicy


@pytest.mark.parametrize("policy_type", [RetryPolicy, HttpRetryPolicy])
class TestRetryPolicyValidation:
    """Validate shared retry construction invariants"""

    @pytest.mark.parametrize("attempts", [0, -1, 1.5, float("nan"), float("inf")])
    def test_invalid_attempts_raise(
        self, policy_type: type[RetryPolicy], attempts: Any
    ) -> None:
        """Reject attempts that cannot describe a positive integer retry budget"""
        with pytest.raises(ValueError, match="max_attempts must be an integer >= 1"):
            policy_type(max_attempts=attempts)

    @pytest.mark.parametrize(
        "field", ["backoff_initial", "backoff_multiplier", "backoff_max"]
    )
    @pytest.mark.parametrize(
        "value", [float("nan"), float("inf"), -float("inf"), -0.01]
    )
    def test_invalid_backoff_raises(
        self, policy_type: type[RetryPolicy], field: str, value: float
    ) -> None:
        """Reject nonfinite and negative backoff values before any request"""
        values: dict[str, Any] = {field: value}
        with pytest.raises(ValueError, match=f"{field} must be finite and >= 0"):
            policy_type(**values)

    def test_valid_boundaries(self, policy_type: type[RetryPolicy]) -> None:
        """Keep single attempts, zero delays and decreasing backoff valid"""
        policy = policy_type(
            max_attempts=1, backoff_initial=0, backoff_multiplier=0.5, backoff_max=0
        )
        assert policy.max_attempts == 1
        assert policy.backoff_initial == 0
        assert policy.backoff_multiplier == 0.5
        assert policy.backoff_max == 0
        assert policy_type(backoff_multiplier=0).backoff_multiplier == 0


class TestCircuitBreakerPolicy:
    """Test suite for CircuitBreakerPolicy."""

    def test_default_values(self) -> None:
        """Validate default field values."""
        policy = CircuitBreakerPolicy()
        assert policy.failure_threshold == 5
        assert policy.recovery_timeout == 30.0
        assert policy.half_open_max_calls == 1
        assert policy.failure_status_codes == frozenset()
        assert policy.count_network_errors is True

    def test_custom_values(self) -> None:
        """Validate that custom values are stored correctly."""
        policy = CircuitBreakerPolicy(
            failure_threshold=3,
            recovery_timeout=10.0,
            half_open_max_calls=2,
            failure_status_codes=frozenset({500, 503}),
            count_network_errors=False,
        )
        assert policy.failure_threshold == 3
        assert policy.recovery_timeout == 10.0
        assert policy.half_open_max_calls == 2
        assert 500 in policy.failure_status_codes
        assert policy.count_network_errors is False

    def test_failure_status_codes_is_frozenset_by_default(self) -> None:
        """Validate failure_status_codes is a frozenset by default."""
        policy = CircuitBreakerPolicy()
        assert isinstance(policy.failure_status_codes, frozenset)

    def test_failure_threshold_below_one_raises(self) -> None:
        """failure_threshold < 1 must raise ValueError."""
        with pytest.raises(ValueError, match="failure_threshold must be >= 1"):
            CircuitBreakerPolicy(failure_threshold=0)

    def test_recovery_timeout_zero_raises(self) -> None:
        """recovery_timeout <= 0 must raise ValueError."""
        with pytest.raises(ValueError, match="recovery_timeout must be > 0"):
            CircuitBreakerPolicy(recovery_timeout=0)

    def test_recovery_timeout_negative_raises(self) -> None:
        """Negative recovery_timeout must raise ValueError."""
        with pytest.raises(ValueError, match="recovery_timeout must be > 0"):
            CircuitBreakerPolicy(recovery_timeout=-1.0)

    def test_half_open_max_calls_below_one_raises(self) -> None:
        """half_open_max_calls < 1 must raise ValueError."""
        with pytest.raises(ValueError, match="half_open_max_calls must be >= 1"):
            CircuitBreakerPolicy(half_open_max_calls=0)


class TestRateLimitPolicy:
    """Test suite for RateLimitPolicy."""

    @pytest.mark.parametrize("field", ["max_requests", "window_seconds"])
    @pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
    def test_nonfinite_values_raise(self, field: str, value: float) -> None:
        """Reject nonfinite limits before they can disable or wedge enforcement"""
        values: dict[str, Any] = {field: value}
        with pytest.raises(ValueError, match=f"{field} must be finite"):
            RateLimitPolicy(**values)

    def test_smallest_request_count_and_positive_window(self) -> None:
        """Accept one request and a finite positive fractional window"""
        policy = RateLimitPolicy(max_requests=1, window_seconds=0.001)
        assert policy.max_requests == 1
        assert policy.window_seconds == 0.001

    def test_default_values(self) -> None:
        """Validate default field values."""
        policy = RateLimitPolicy()
        assert policy.max_requests == 100
        assert policy.window_seconds == 60.0

    def test_custom_values(self) -> None:
        """Validate that custom values are stored correctly."""
        policy = RateLimitPolicy(max_requests=10, window_seconds=5.0)
        assert policy.max_requests == 10
        assert policy.window_seconds == 5.0

    def test_max_requests_below_one_raises(self) -> None:
        """max_requests < 1 must raise ValueError."""
        with pytest.raises(ValueError, match="max_requests must be >= 1"):
            RateLimitPolicy(max_requests=0)

    def test_window_seconds_zero_raises(self) -> None:
        """window_seconds <= 0 must raise ValueError."""
        with pytest.raises(ValueError, match="window_seconds must be > 0"):
            RateLimitPolicy(window_seconds=0)

    def test_window_seconds_negative_raises(self) -> None:
        """Negative window_seconds must raise ValueError."""
        with pytest.raises(ValueError, match="window_seconds must be > 0"):
            RateLimitPolicy(window_seconds=-10.0)
