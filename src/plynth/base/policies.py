"""Protocol-agnostic retry policy for Plynth transports.

Defines ``RetryPolicy``, a dataclass that controls retry behaviour.
Middleware implementations (``RetryMiddleware``, ``AsyncRetryMiddleware``)
live in ``plynth.middleware.retry``.

The retry loop checks ``retryable_status_codes`` (empty by default) so
the base policy works for both core and HTTP transports without
HTTP-specific logic. Override via ``HttpRetryPolicy`` in
``plynth.http.policies`` to add HTTP-specific codes (e.g. 429, 503).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

__all__ = ["CircuitBreakerPolicy", "RateLimitPolicy", "RetryPolicy"]


def _default_retryable_exception(exc: BaseException) -> bool:
    """Return whether an exception should be retried by default.

    The default focuses on low-level network/protocol failures and excludes
    generic programming errors.
    """
    return isinstance(exc, (TimeoutError, ConnectionError, OSError))


@dataclass
class RetryPolicy:
    """Controls retry and back-off behaviour for a transport.

    Attributes:
        max_attempts: Total number of attempts, including the first.
            ``1`` means no retries. Must be >= 1.
        backoff_initial: Delay in seconds before the second attempt.
        backoff_multiplier: Factor by which the delay grows per attempt.
        backoff_max: Upper bound for the computed delay in seconds.
        retry_on_network_error: When ``True``, network-level exceptions
            (e.g. connection reset) trigger a retry. When ``False``,
            they are re-raised immediately.
        retryable_status_codes: Set of response status codes that trigger
            a retry. Empty by default — override in ``HttpRetryPolicy``
            to add HTTP-specific codes (e.g. 429, 503).
        retryable_exception_classifier: Callable that decides whether an
            exception is retryable when ``retry_on_network_error`` is true.
            Defaults to a network/protocol-focused classifier.

    Example::

        from plynth.base.policies import RetryPolicy

        policy = RetryPolicy(max_attempts=3, backoff_initial=1.0)

    """

    max_attempts: int = 3
    backoff_initial: float = 0.5
    backoff_multiplier: float = 2.0
    backoff_max: float = 30.0
    retry_on_network_error: bool = True
    retryable_status_codes: frozenset[int] = field(default_factory=frozenset)
    retryable_exception_classifier: Callable[[BaseException], bool] = (
        _default_retryable_exception
    )


@dataclass
class CircuitBreakerPolicy:
    """Controls circuit breaker behaviour for transport middleware.

    Attributes:
        failure_threshold: Number of consecutive failures before opening
            the circuit.
        recovery_timeout: Seconds to keep the circuit open before allowing
            a half-open probe call.
        half_open_max_calls: Number of allowed probe calls while the
            breaker is half-open.
        failure_status_codes: Response status codes that count as failures.
            Empty by default, so only classified exceptions count.
        count_network_errors: When ``True``, classified exceptions count as
            failures.
        failure_exception_classifier: Callable that decides whether an
            exception should count as a failure.

    """

    failure_threshold: int = 5
    recovery_timeout: float = 30.0
    half_open_max_calls: int = 1
    failure_status_codes: frozenset[int] = field(default_factory=frozenset)
    count_network_errors: bool = True
    failure_exception_classifier: Callable[[BaseException], bool] = (
        _default_retryable_exception
    )

    def __post_init__(self) -> None:
        """Validate policy values."""
        if self.failure_threshold < 1:
            raise ValueError("failure_threshold must be >= 1")
        if self.recovery_timeout <= 0:
            raise ValueError("recovery_timeout must be > 0")
        if self.half_open_max_calls < 1:
            raise ValueError("half_open_max_calls must be >= 1")


@dataclass
class RateLimitPolicy:
    """Controls request-rate limiting for transport middleware.

    Attributes:
        max_requests: Maximum number of requests allowed in each time
            window.
        window_seconds: Window size in seconds.

    """

    max_requests: int = 100
    window_seconds: float = 60.0

    def __post_init__(self) -> None:
        """Validate policy values."""
        if self.max_requests < 1:
            raise ValueError("max_requests must be >= 1")
        if self.window_seconds <= 0:
            raise ValueError("window_seconds must be > 0")
