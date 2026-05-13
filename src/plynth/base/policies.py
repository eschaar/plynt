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

__all__ = ["RetryPolicy"]


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
