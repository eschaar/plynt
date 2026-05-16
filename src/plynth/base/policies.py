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
from enum import Enum

__all__ = [
    "CircuitBreakerPolicy",
    "RateLimitPolicy",
    "RetryPolicy",
    "ThrottleGovernanceAction",
    "ThrottleGovernanceDecision",
    "ThrottleGovernancePolicy",
    "ThrottleSignal",
]


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


class ThrottleGovernanceAction(Enum):
    """Possible actions emitted by throttle governance policy.

    Attributes:
        PROCEED: Allow the request to proceed normally.
        DELAY: Wait before the next attempt; retry will use the delay.
        REJECT: Fail fast; do not attempt retry.

    """

    PROCEED = "proceed"
    DELAY = "delay"
    REJECT = "reject"


@dataclass
class ThrottleSignal:
    """Normalized upstream throttle signal from external API.

    Connectors and client adapters normalize provider-specific headers
    (e.g. Retry-After, X-RateLimit-Reset) into this unified model.

    Attributes:
        detected: Whether throttling was detected.
        retry_after_seconds: Delay in seconds suggested by upstream,
            if available.
        reset_at_seconds: Unix timestamp when throttle clears, if available.
        remaining_quota: Remaining requests in quota window, if available.
        quota_limit: Total request limit in quota window, if available.

    """

    detected: bool
    retry_after_seconds: float | None = None
    reset_at_seconds: float | None = None
    remaining_quota: int | None = None
    quota_limit: int | None = None


@dataclass
class ThrottleGovernanceDecision:
    """Decision output from throttle governance policy.

    Attributes:
        action: Governance action to take (PROCEED, DELAY, REJECT).
        delay_seconds: When action is DELAY, the recommended wait time.
            Retry integrations use max(backoff, delay_seconds).
        reason: Human-readable reason for the decision (debug/logging).

    """

    action: ThrottleGovernanceAction
    delay_seconds: float = 0.0
    reason: str = ""


@dataclass
class ThrottleGovernancePolicy:
    """Controls governance behavior for upstream throttling.

    When upstream APIs send throttle signals (429, 503 with retry delays,
    quota exhaustion, etc.), this policy decides what to do: proceed,
    delay, or reject.

    Attributes:
        reject_on_detection: When ``True``, any detected throttle signal
            causes immediate rejection instead of attempting delay + retry.
        min_delay_seconds: Minimum delay to apply when throttled, even if
            upstream suggests less. Prevents aggressive retry storms.
        max_delay_seconds: Upper bound for governance delay. If upstream
            suggests longer delay, it is clamped to this value.

    Example::

        from plynth.base.policies import ThrottleGovernancePolicy

        policy = ThrottleGovernancePolicy(
            reject_on_detection=False,
            min_delay_seconds=1.0,
            max_delay_seconds=60.0,
        )

    """

    reject_on_detection: bool = False
    min_delay_seconds: float = 0.5
    max_delay_seconds: float = 60.0

    def __post_init__(self) -> None:
        """Validate policy values."""
        if self.min_delay_seconds < 0:
            raise ValueError("min_delay_seconds must be >= 0")
        if self.max_delay_seconds < self.min_delay_seconds:
            raise ValueError("max_delay_seconds must be >= min_delay_seconds")

    def evaluate(self, signal: ThrottleSignal) -> ThrottleGovernanceDecision:
        """Evaluate a throttle signal and return a governance decision.

        Args:
            signal: Normalized throttle signal from upstream API.

        Returns:
            Governance decision with action and delay (if applicable).

        """
        if not signal.detected:
            return ThrottleGovernanceDecision(
                action=ThrottleGovernanceAction.PROCEED,
                reason="No throttle detected",
            )

        if self.reject_on_detection:
            return ThrottleGovernanceDecision(
                action=ThrottleGovernanceAction.REJECT,
                reason="Throttle detected and reject_on_detection=True",
            )

        # Compute delay from signal
        delay = signal.retry_after_seconds or self.min_delay_seconds
        delay = max(delay, self.min_delay_seconds)
        delay = min(delay, self.max_delay_seconds)

        return ThrottleGovernanceDecision(
            action=ThrottleGovernanceAction.DELAY,
            delay_seconds=delay,
            reason=f"Throttled; delaying {delay}s",
        )
