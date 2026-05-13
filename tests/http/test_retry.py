"""Tests for plynth.http.policies.HttpRetryPolicy."""

from __future__ import annotations

from http import HTTPStatus

from plynth.base.policies import RetryPolicy
from plynth.http.policies import HttpRetryPolicy


class TestHttpRetryPolicy:
    """Test suite for HttpRetryPolicy."""

    def test_default_values(self) -> None:
        """Validate default values."""
        policy = HttpRetryPolicy()
        assert policy.max_attempts == 3
        assert policy.backoff_initial == 0.5
        assert policy.backoff_multiplier == 2.0
        assert policy.backoff_max == 30.0
        assert policy.retry_on_network_error is True
        assert policy.retryable_status_codes == frozenset(
            {
                HTTPStatus.TOO_MANY_REQUESTS,
                HTTPStatus.INTERNAL_SERVER_ERROR,
                HTTPStatus.BAD_GATEWAY,
                HTTPStatus.SERVICE_UNAVAILABLE,
                HTTPStatus.GATEWAY_TIMEOUT,
            }
        )

    def test_inherits_from_retry_policy(self) -> None:
        """Validate inherits from retry policy."""
        assert issubclass(HttpRetryPolicy, RetryPolicy)

    def test_custom_retryable_status_codes_replaces_defaults(self) -> None:
        """Providing retryable_status_codes replaces the defaults entirely."""
        policy = HttpRetryPolicy(
            retryable_status_codes=frozenset(
                {
                    HTTPStatus.TOO_MANY_REQUESTS,
                    HTTPStatus.SERVICE_UNAVAILABLE,
                }
            )
        )
        assert policy.retryable_status_codes == frozenset(
            {
                HTTPStatus.TOO_MANY_REQUESTS,
                HTTPStatus.SERVICE_UNAVAILABLE,
            }
        )
        # Default codes not included in the override must be absent.
        assert HTTPStatus.INTERNAL_SERVER_ERROR not in policy.retryable_status_codes
        assert HTTPStatus.BAD_GATEWAY not in policy.retryable_status_codes
        assert HTTPStatus.GATEWAY_TIMEOUT not in policy.retryable_status_codes

    def test_custom_max_attempts(self) -> None:
        """Validate custom max attempts."""
        policy = HttpRetryPolicy(max_attempts=5)
        assert policy.max_attempts == 5

    def test_status_codes_are_frozenset(self) -> None:
        """Validate status codes are frozenset."""
        policy = HttpRetryPolicy()
        assert isinstance(policy.retryable_status_codes, frozenset)

    def test_status_codes_accept_raw_integers(self) -> None:
        """Raw integers are valid alongside HTTPStatus values (IntEnum is int)."""
        policy = HttpRetryPolicy(retryable_status_codes=frozenset({429, 503}))
        assert 429 in policy.retryable_status_codes
        assert HTTPStatus.SERVICE_UNAVAILABLE in policy.retryable_status_codes
