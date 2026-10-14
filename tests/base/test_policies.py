"""Tests for plynt.base.policies.CircuitBreakerPolicy and RateLimitPolicy."""

from __future__ import annotations

import pytest

from plynt.base.policies import CircuitBreakerPolicy, RateLimitPolicy


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
