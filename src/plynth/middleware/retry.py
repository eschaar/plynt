"""Protocol-agnostic retry policy and middleware for Plynth transports.

Defines ``RetryMiddleware`` / ``AsyncRetryMiddleware``, which apply a
``RetryPolicy`` as first-class middleware in the transport's middleware chain.

Both classes share ``_RetryBase``, which owns the policy reference and the
backoff delay calculation. Only the ``handle`` method differs: the sync
variant uses ``time.sleep``; the async variant uses ``asyncio.sleep``.

The retry loop checks ``retryable_status_codes`` (empty by default) so
the base classes work for both core and HTTP transports without
HTTP-specific logic. Override via ``HttpRetryPolicy`` in
``plynth.http.policies`` to add HTTP-specific codes (e.g. 429, 503).

When throttle governance middleware is in the chain, governance decisions
(if a delay is recommended) are attached to the response object. The retry
loop respects governance delay by using ``max(backoff, governance_delay)``
as the wait time before the next attempt.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable

from plynth.base.middleware import AsyncMiddleware, SyncMiddleware
from plynth.base.policies import RetryPolicy
from plynth.base.request import Request
from plynth.base.response import Response

__all__ = ["AsyncRetryMiddleware", "RetryMiddleware"]

_logger = logging.getLogger(__name__)


class _RetryBase:  # pylint: disable=too-few-public-methods
    """Shared state and backoff logic for RetryMiddleware / AsyncRetryMiddleware.

    Not intended for direct use. Subclass ``RetryMiddleware`` or
    ``AsyncRetryMiddleware`` instead.
    """

    def __init__(self, policy: RetryPolicy) -> None:
        """Initialize _RetryBase."""
        self._policy = policy

    def _backoff_delay(self, attempt: int) -> float:
        """Return the capped exponential back-off delay in seconds for *attempt*."""
        return min(
            self._policy.backoff_initial
            * (self._policy.backoff_multiplier ** (attempt - 1)),
            self._policy.backoff_max,
        )

    def _effective_delay(
        self,
        backoff_delay: float,
        response: Response | None = None,
    ) -> float:
        """Calculate effective delay, respecting governance delay if present.

        When throttle governance middleware is in the chain, it may attach
        a governance_delay to the response object. This represents the
        minimum wait time suggested by upstream API throttle signals.

        The effective delay is ``max(backoff, governance_delay)`` to ensure
        governance delay takes precedence if it's longer.

        Args:
            backoff_delay: Computed backoff delay in seconds.
            response: Response object (may have governance delay attached).

        Returns:
            Effective delay in seconds.

        """
        if response is None:
            return backoff_delay

        governance_delay = getattr(response, "_governance_delay_seconds", 0.0)
        return max(backoff_delay, governance_delay)


class RetryMiddleware(  # pylint: disable=too-few-public-methods
    _RetryBase,
    SyncMiddleware,
):
    """Sync middleware that retries requests according to a ``RetryPolicy``.

    Wraps the inner ``next_handler`` call in a retry loop with configurable
    back-off. Retries on transient HTTP status codes (as defined by the
    policy) and optionally on network-level exceptions.

    Place ``RetryMiddleware`` inside auth middleware in the chain so that
    every retry attempt already carries valid credentials::

        middlewares = [
            OAuth2AuthMiddleware(...),  # outermost
            RetryMiddleware(policy),    # innermost above I/O
        ]

    Args:
        policy: The retry policy that controls attempts, back-off, and
            retryable status codes.

    """

    def handle(
        self,
        request: Request,
        next_handler: Callable[[Request], Response],
    ) -> Response:
        """Execute the retry loop, delegating each attempt to *next_handler*.

        Returns:
            The response from the first non-retryable attempt, or the
            last response once all attempts are exhausted.

        Raises:
            Exception: Re-raises the last network exception when all
                attempts raise and ``retry_on_network_error`` is ``True``.

        """
        policy = self._policy
        if policy.max_attempts <= 1:
            return next_handler(request)

        last_exc: BaseException | None = None
        response: Response | None = None

        for attempt in range(policy.max_attempts):
            if attempt > 0:
                backoff = self._backoff_delay(attempt)
                delay = self._effective_delay(backoff, response)
                _logger.debug(
                    "Retry attempt %d/%d after %.2fs delay.",
                    attempt + 1,
                    policy.max_attempts,
                    delay,
                )
                time.sleep(delay)

            try:
                response = next_handler(request)
            except Exception as exc:  # pylint: disable=broad-exception-caught
                if not policy.retry_on_network_error:
                    raise
                if not policy.retryable_exception_classifier(exc):
                    raise
                last_exc = exc
                response = None
                _logger.debug(
                    "Attempt %d/%d raised %s: %s",
                    attempt + 1,
                    policy.max_attempts,
                    type(exc).__name__,
                    exc,
                )
                continue

            last_exc = None
            if response.status_code not in policy.retryable_status_codes:
                return response
            _logger.debug(
                "Attempt %d/%d got retryable status %d.",
                attempt + 1,
                policy.max_attempts,
                response.status_code,
            )

        if last_exc is not None:
            _logger.warning(
                "All %d retry attempts exhausted with a network error: %s",
                policy.max_attempts,
                last_exc,
            )
            raise last_exc

        if response is None:  # pragma: no cover
            raise RuntimeError("Retry loop ended without a response or exception.")

        _logger.warning(
            "All %d retry attempts exhausted — final status %d.",
            policy.max_attempts,
            response.status_code,
        )
        return response


class AsyncRetryMiddleware(  # pylint: disable=too-few-public-methods
    _RetryBase,
    AsyncMiddleware,
):
    """Async middleware that retries requests according to a ``RetryPolicy``.

    Async counterpart of ``RetryMiddleware``. Uses ``asyncio.sleep`` for
    non-blocking back-off between attempts.

    Args:
        policy: The retry policy that controls attempts, back-off, and
            retryable status codes.

    """

    async def handle(
        self,
        request: Request,
        next_handler: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Execute the async retry loop, delegating each attempt to *next_handler*.

        Returns:
            The response from the first non-retryable attempt, or the
            last response once all attempts are exhausted.

        Raises:
            Exception: Re-raises the last network exception when all
                attempts raise and ``retry_on_network_error`` is ``True``.

        """
        policy = self._policy
        if policy.max_attempts <= 1:
            return await next_handler(request)

        last_exc: BaseException | None = None
        response: Response | None = None

        for attempt in range(policy.max_attempts):
            if attempt > 0:
                backoff = self._backoff_delay(attempt)
                delay = self._effective_delay(backoff, response)
                _logger.debug(
                    "Retry attempt %d/%d after %.2fs delay.",
                    attempt + 1,
                    policy.max_attempts,
                    delay,
                )
                await asyncio.sleep(delay)

            try:
                response = await next_handler(request)
            except Exception as exc:  # pylint: disable=broad-exception-caught
                if not policy.retry_on_network_error:
                    raise
                if not policy.retryable_exception_classifier(exc):
                    raise
                last_exc = exc
                response = None
                _logger.debug(
                    "Attempt %d/%d raised %s: %s",
                    attempt + 1,
                    policy.max_attempts,
                    type(exc).__name__,
                    exc,
                )
                continue

            last_exc = None
            if response.status_code not in policy.retryable_status_codes:
                return response
            _logger.debug(
                "Attempt %d/%d got retryable status %d.",
                attempt + 1,
                policy.max_attempts,
                response.status_code,
            )

        if last_exc is not None:
            _logger.warning(
                "All %d retry attempts exhausted with a network error: %s",
                policy.max_attempts,
                last_exc,
            )
            raise last_exc

        if response is None:  # pragma: no cover
            raise RuntimeError("Retry loop ended without a response or exception.")

        _logger.warning(
            "All %d retry attempts exhausted — final status %d.",
            policy.max_attempts,
            response.status_code,
        )
        return response
