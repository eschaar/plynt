"""HTTP-specific retry policy for Plynth.

Extends ``plynth.base.policies.RetryPolicy`` with HTTP status codes that
should trigger a retry in addition to network-level failures.

The base ``RetryPolicy`` is protocol-agnostic and lives in
``plynth.base.policies`` so non-HTTP transports (e.g. gRPC) can use it too.
``HttpRetryPolicy`` adds the concept of retryable HTTP status codes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from http import HTTPStatus

from plynth.base.policies import RetryPolicy

__all__ = ["HttpRetryPolicy"]


@dataclass
class HttpRetryPolicy(RetryPolicy):
    """Retry policy that also retries on specific HTTP status codes.

    Inherits all back-off fields from ``RetryPolicy`` and adds
    ``retryable_status_codes``, which causes the retry loop to retry
    when the server returns one of those codes.

    .. note::
        Providing ``retryable_status_codes`` **replaces** the defaults
        entirely — it does not extend them.  To add a code to the
        default set, include all codes explicitly.

    Attributes:
        retryable_status_codes: HTTP status codes that trigger a retry.
            Defaults to ``{429, 500, 502, 503, 504}``
            (``TOO_MANY_REQUESTS``, ``INTERNAL_SERVER_ERROR``,
            ``BAD_GATEWAY``, ``SERVICE_UNAVAILABLE``,
            ``GATEWAY_TIMEOUT``).

    Example::

        from http import HTTPStatus
        from plynth.http.policies import HttpRetryPolicy

        # Only retry on rate-limit and service unavailable.
        policy = HttpRetryPolicy(
            max_attempts=4,
            retryable_status_codes=frozenset({
                HTTPStatus.TOO_MANY_REQUESTS,
                HTTPStatus.SERVICE_UNAVAILABLE,
            }),
        )

    """

    retryable_status_codes: frozenset[int] = field(
        default_factory=lambda: frozenset(
            {
                HTTPStatus.TOO_MANY_REQUESTS,
                HTTPStatus.INTERNAL_SERVER_ERROR,
                HTTPStatus.BAD_GATEWAY,
                HTTPStatus.SERVICE_UNAVAILABLE,
                HTTPStatus.GATEWAY_TIMEOUT,
            }
        )
    )
