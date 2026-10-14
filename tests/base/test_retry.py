"""Tests for plynt.base.policies.RetryPolicy."""

from __future__ import annotations

from plynt.base.policies import RetryPolicy


class TestRetryPolicy:
    """Test suite for RetryPolicy."""

    def test_default_values(self) -> None:
        """Validate default values."""
        policy = RetryPolicy()
        assert policy.max_attempts == 3
        assert policy.backoff_initial == 0.5
        assert policy.backoff_multiplier == 2.0
        assert policy.backoff_max == 30.0
        assert policy.retry_on_network_error is True
        assert policy.retryable_status_codes == frozenset()

    def test_custom_values(self) -> None:
        """Validate custom values."""
        policy = RetryPolicy(
            max_attempts=5,
            backoff_initial=1.0,
            backoff_multiplier=3.0,
            backoff_max=60.0,
            retry_on_network_error=False,
            retryable_status_codes=frozenset({503}),
        )
        assert policy.max_attempts == 5
        assert policy.backoff_initial == 1.0
        assert policy.backoff_multiplier == 3.0
        assert policy.backoff_max == 60.0
        assert policy.retry_on_network_error is False
        assert 503 in policy.retryable_status_codes

    def test_retryable_status_codes_is_frozenset_by_default(self) -> None:
        """Validate retryable status codes is frozenset by default."""
        policy = RetryPolicy()
        assert isinstance(policy.retryable_status_codes, frozenset)
        assert len(policy.retryable_status_codes) == 0

    def test_default_exception_classifier_retries_network_exceptions(self) -> None:
        """Validate default classifier marks network/protocol exceptions retryable."""
        policy = RetryPolicy()
        classify = policy.retryable_exception_classifier

        assert classify(ConnectionError("network")) is True
        assert classify(TimeoutError("timeout")) is True
        assert classify(OSError("socket")) is True

    def test_default_exception_classifier_skips_programming_exceptions(self) -> None:
        """Validate default classifier skips non-network exceptions."""
        policy = RetryPolicy()
        assert policy.retryable_exception_classifier(ValueError("bad input")) is False
