"""HTTP-specific retry policy for Plynt.

Extends ``plynt.base.policies.RetryPolicy`` with HTTP status codes that
should trigger a retry in addition to network-level failures.

The base ``RetryPolicy`` is protocol-agnostic and lives in
``plynt.base.policies`` so non-HTTP transports (e.g. gRPC) can use it too.
``HttpRetryPolicy`` adds the concept of retryable HTTP status codes.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from http import HTTPStatus

from plynt.base.policies import RetryPolicy, _default_retryable_exception

try:
    from httpx2 import NetworkError, ProxyError, RemoteProtocolError, TimeoutException
except ModuleNotFoundError as exc:  # pragma: no cover - clean core wheel smoke
    if exc.name != "httpx2":
        raise
    _HTTPX_NETWORK_ERRORS: tuple[type[BaseException], ...] = ()
else:
    _HTTPX_NETWORK_ERRORS = (
        NetworkError,
        ProxyError,
        RemoteProtocolError,
        TimeoutException,
    )

__all__ = ["HttpRetryPolicy"]


def _default_http_retryable_exception(exc: BaseException) -> bool:
    """Recognize built-in and optional HTTP backend network errors (ADR-0038)"""
    return _default_retryable_exception(exc) or isinstance(exc, _HTTPX_NETWORK_ERRORS)


@dataclass
class HttpRetryPolicy(RetryPolicy):
    """Retry policy that also retries on specific HTTP status codes.

    Inherits all back-off fields from ``RetryPolicy`` and adds
    ``retryable_status_codes``, which causes the retry loop to retry
    when the server returns one of those codes. The default exception
    classifier also recognizes httpx2 network, timeout, remote protocol,
    and proxy errors when the optional backend is installed. An explicit
    classifier replaces this default.

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
        from plynt.http.policies import HttpRetryPolicy

        # Only retry on rate-limit and service unavailable.
        policy = HttpRetryPolicy(
            max_attempts=4,
            retryable_status_codes=frozenset({
                HTTPStatus.TOO_MANY_REQUESTS,
                HTTPStatus.SERVICE_UNAVAILABLE,
            }),
        )

    """

    retryable_exception_classifier: Callable[[BaseException], bool] = (
        _default_http_retryable_exception
    )
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
