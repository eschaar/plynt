"""Throttle middleware for handling upstream throttle signals.

Detects upstream throttle signals sent by external APIs (e.g. 429 responses,
503 with Retry-After headers, quota exhaustion hints) and applies a
deterministic governance policy to decide whether to proceed, delay, or
reject the request.

Governance decisions can be consumed by retry middleware to enforce delays
that take precedence over retry backoff calculations.

Classes:
    - ``ThrottleGovernedError``: Exception raised when governance rejects.
    - ``ThrottleGovernanceMiddleware``: Sync middleware.
    - ``AsyncThrottleGovernanceMiddleware``: Async middleware.

"""

from __future__ import annotations

import math
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from http import HTTPStatus
from typing import TYPE_CHECKING

from plynth.base.middleware import (
    AsyncMiddleware,
    NextAsyncHandler,
    NextSyncHandler,
    SyncMiddleware,
)
from plynth.base.policies import (
    ThrottleGovernanceAction,
    ThrottleGovernancePolicy,
    ThrottleSignal,
)
from plynth.base.response import Response

if TYPE_CHECKING:
    from plynth.base.request import Request

__all__ = [
    "AsyncThrottleGovernanceMiddleware",
    "ThrottleGovernanceMiddleware",
    "ThrottleGovernedError",
]


class ThrottleGovernedError(Exception):
    """Raised when throttle governance rejects a request.

    Attributes:
        response: The upstream response that triggered rejection.
        delay_seconds: Suggested delay before retry (if applicable).
        reason: Human-readable reason from governance policy.

    """

    def __init__(
        self,
        response: Response,
        delay_seconds: float = 0.0,
        reason: str = "",
    ) -> None:
        """Initialize throttle governed error."""
        self.response = response
        self.delay_seconds = delay_seconds
        self.reason = reason
        message = f"Throttle governance rejected request: {reason}"
        super().__init__(message)


def _extract_throttle_signal(response: Response) -> ThrottleSignal:
    """Extract normalized throttle signal from HTTP response.

    Looks for common upstream throttle indicators:
    - 429 Too Many Requests (always throttle)
    - 503 Service Unavailable with Retry-After (often throttle)
    - Any Retry-After header (indicates backpressure)
    - X-RateLimit-Remaining: 0 (quota exhaustion)

    Args:
        response: HTTP response to inspect.

    Returns:
        Normalized throttle signal.

    """
    # 429 is always throttle
    if response.status_code == HTTPStatus.TOO_MANY_REQUESTS:
        signal = ThrottleSignal(detected=True)
        signal.retry_after_seconds = _parse_retry_after(response)
        signal.reset_at_seconds = _parse_reset_at(response)
        return signal

    # 503 with Retry-After can indicate throttle
    if response.status_code == HTTPStatus.SERVICE_UNAVAILABLE:
        retry_after = _parse_retry_after(response)
        if retry_after is not None:
            signal = ThrottleSignal(detected=True)
            signal.retry_after_seconds = retry_after
            signal.reset_at_seconds = _parse_reset_at(response)
            return signal

    # Check for rate limit exhaustion via headers
    if _is_quota_exhausted(response):
        signal = ThrottleSignal(detected=True)
        signal.retry_after_seconds = _parse_retry_after(response)
        signal.reset_at_seconds = _parse_reset_at(response)
        return signal

    # No throttle signal detected
    return ThrottleSignal(detected=False)


def _parse_retry_after(response: Response) -> float | None:
    """Parse Retry-After header into seconds.

    Retry-After can be:
    - Decimal seconds: "120"
    - HTTP date: "Wed, 21 Oct 2026 07:28:00 GMT" (converted to seconds)

    Args:
        response: HTTP response to inspect.

    Returns:
        Retry-after delay in seconds, or None if not found or unparseable.

    """
    retry_after = {k.lower(): v for k, v in response.headers.items()}.get("retry-after")
    if not retry_after:
        return None

    # Try parsing as seconds (most common)
    try:
        value = float(retry_after)
        if not math.isfinite(value):
            return None
        return value
    except ValueError:
        pass

    # Try parsing as HTTP-date
    try:
        parsed_date = parsedate_to_datetime(retry_after)
        now = datetime.now(UTC)
        delay = (parsed_date - now).total_seconds()
        return max(0, delay)  # Don't return negative delays
    except (TypeError, ValueError):
        pass

    return None


def _parse_reset_at(response: Response) -> float | None:
    """Parse X-RateLimit-Reset header into a Unix timestamp.

    Args:
        response: HTTP response to inspect.

    Returns:
        Unix timestamp in seconds, or None if not present or unparseable.

    """
    headers_lower = {k.lower(): v for k, v in response.headers.items()}
    reset_at = headers_lower.get("x-ratelimit-reset")
    if not reset_at:
        return None
    try:
        return float(reset_at)
    except ValueError:
        return None


def _is_quota_exhausted(response: Response) -> bool:
    """Check if response indicates quota exhaustion.

    Looks for X-RateLimit-Remaining: 0 or similar quota-exhaustion signals.

    Args:
        response: HTTP response to inspect.

    Returns:
        True if quota appears exhausted.

    """
    remaining = {k.lower(): v for k, v in response.headers.items()}.get(
        "x-ratelimit-remaining"
    )
    if remaining == "0":
        return True

    return False


class ThrottleGovernanceMiddleware(SyncMiddleware):
    """Sync middleware that applies throttle governance policy.

    Intercepts responses, detects upstream throttle signals, and applies
    governance logic to decide whether to proceed, delay, or reject.

    """

    def __init__(
        self,
        policy: ThrottleGovernancePolicy | None = None,
    ) -> None:
        """Initialize throttle governance middleware.

        Args:
            policy: Governance policy (default: reject_on_detection=False).

        """
        self._policy = policy or ThrottleGovernancePolicy()

    def handle(self, request: Request, next_handler: NextSyncHandler) -> Response:
        """Apply throttle governance to request/response cycle.

        Args:
            request: Outgoing HTTP request.
            next_handler: Next handler in the middleware chain.

        Returns:
            Response from the upstream handler.

        Raises:
            ThrottleGovernedError: If governance rejects the request.

        """
        response = next_handler(request)

        # Extract and evaluate throttle signal
        signal = _extract_throttle_signal(response)
        decision = self._policy.evaluate(signal)

        # Apply governance action
        if decision.action == ThrottleGovernanceAction.PROCEED:
            return response

        if decision.action == ThrottleGovernanceAction.REJECT:
            raise ThrottleGovernedError(
                response=response,
                delay_seconds=decision.delay_seconds,
                reason=decision.reason,
            )

        # DELAY action: store governance delay on response for retry to use.
        # Keep these attributes dynamic to avoid coupling Response to policy.
        response.__dict__["_governance_delay_seconds"] = decision.delay_seconds
        response.__dict__["_governance_reason"] = decision.reason
        return response


class AsyncThrottleGovernanceMiddleware(AsyncMiddleware):
    """Async middleware that applies throttle governance policy.

    Intercepts responses, detects upstream throttle signals, and applies
    governance logic to decide whether to proceed, delay, or reject.

    """

    def __init__(
        self,
        policy: ThrottleGovernancePolicy | None = None,
    ) -> None:
        """Initialize async throttle governance middleware.

        Args:
            policy: Governance policy (default: reject_on_detection=False).

        """
        self._policy = policy or ThrottleGovernancePolicy()

    async def handle(
        self, request: Request, next_handler: NextAsyncHandler
    ) -> Response:
        """Apply throttle governance to async request/response cycle.

        Args:
            request: Outgoing HTTP request.
            next_handler: Next handler in the middleware chain.

        Returns:
            Response from the upstream handler.

        Raises:
            ThrottleGovernedError: If governance rejects the request.

        """
        response_obj = await next_handler(request)
        if not isinstance(response_obj, Response):
            raise TypeError("next_handler must return Response")
        response = response_obj

        # Extract and evaluate throttle signal
        signal = _extract_throttle_signal(response)
        decision = self._policy.evaluate(signal)

        # Apply governance action
        if decision.action == ThrottleGovernanceAction.PROCEED:
            return response

        if decision.action == ThrottleGovernanceAction.REJECT:
            raise ThrottleGovernedError(
                response=response,
                delay_seconds=decision.delay_seconds,
                reason=decision.reason,
            )

        # DELAY action: store governance delay on response for retry to use.
        response.__dict__["_governance_delay_seconds"] = decision.delay_seconds
        response.__dict__["_governance_reason"] = decision.reason
        return response
