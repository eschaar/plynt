"""Protocol-agnostic request-rate-limit middleware for Plynth transports."""

from __future__ import annotations

import asyncio
import threading
import time
from collections import deque
from collections.abc import Awaitable, Callable

from plynth.base.middleware import AsyncMiddleware, SyncMiddleware
from plynth.base.policies import RateLimitPolicy
from plynth.base.request import Request
from plynth.base.response import Response

__all__ = [
    "AsyncRateLimitMiddleware",
    "RateLimitExceededError",
    "RateLimitMiddleware",
]


class RateLimitExceededError(RuntimeError):
    """Raised when middleware rejects a request due to rate limiting."""

    def __init__(self, retry_after_seconds: float) -> None:
        """Initialize RateLimitExceededError."""
        self.retry_after_seconds = max(0.0, retry_after_seconds)
        super().__init__(
            f"Rate limit exceeded. Retry after {self.retry_after_seconds:.3f}s."
        )


class _RateLimitWindow:
    """Sliding-window counter for rate limiting."""

    def __init__(self, policy: RateLimitPolicy) -> None:
        """Initialize _RateLimitWindow."""
        self._policy = policy
        self._timestamps: deque[float] = deque()

    def acquire(self, *, now: float) -> None:
        """Acquire one request slot or raise ``RateLimitExceededError``."""
        lower_bound = now - self._policy.window_seconds
        while self._timestamps and self._timestamps[0] <= lower_bound:
            self._timestamps.popleft()

        if len(self._timestamps) >= self._policy.max_requests:
            retry_after = self._policy.window_seconds - (now - self._timestamps[0])
            raise RateLimitExceededError(retry_after)

        self._timestamps.append(now)


class RateLimitMiddleware(SyncMiddleware):
    """Sync request-rate-limit middleware with a sliding window."""

    def __init__(self, policy: RateLimitPolicy) -> None:
        """Initialize RateLimitMiddleware."""
        self._window = _RateLimitWindow(policy)
        self._lock = threading.Lock()

    def handle(
        self,
        request: Request,
        next_handler: Callable[[Request], Response],
    ) -> Response:
        """Process a request through the rate limiter."""
        with self._lock:
            self._window.acquire(now=time.monotonic())
        return next_handler(request)


class AsyncRateLimitMiddleware(AsyncMiddleware):
    """Async request-rate-limit middleware with a sliding window."""

    def __init__(self, policy: RateLimitPolicy) -> None:
        """Initialize AsyncRateLimitMiddleware."""
        self._window = _RateLimitWindow(policy)
        self._lock = asyncio.Lock()

    async def handle(
        self,
        request: Request,
        next_handler: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Process a request through the async rate limiter."""
        async with self._lock:
            self._window.acquire(now=time.monotonic())
        return await next_handler(request)
