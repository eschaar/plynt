"""Protocol-agnostic circuit breaker middleware for Plynt transports."""

from __future__ import annotations

import asyncio
import threading
import time
from collections.abc import Awaitable, Callable

from plynt.base.middleware import AsyncMiddleware, SyncMiddleware
from plynt.base.policies import CircuitBreakerPolicy
from plynt.base.request import Request
from plynt.base.response import Response

__all__ = [
    "AsyncCircuitBreakerMiddleware",
    "CircuitBreakerMiddleware",
    "CircuitBreakerOpenError",
]


class CircuitBreakerOpenError(RuntimeError):
    """Raised when a circuit breaker rejects a request while open."""

    def __init__(self, retry_after_seconds: float) -> None:
        """Initialize CircuitBreakerOpenError."""
        self.retry_after_seconds = max(0.0, retry_after_seconds)
        super().__init__(
            f"Circuit is open. Retry after {self.retry_after_seconds:.3f}s."
        )


class _CircuitBreakerState:
    """Shared state machine for sync and async circuit breaker middleware."""

    def __init__(self, policy: CircuitBreakerPolicy) -> None:
        """Initialize _CircuitBreakerState."""
        self._policy = policy
        self._state = "closed"
        self._opened_at = 0.0
        self._failure_count = 0
        self._half_open_calls = 0

    def before_call(self, *, now: float) -> None:
        """Validate whether a request may proceed."""
        if self._state == "open":
            elapsed = now - self._opened_at
            if elapsed < self._policy.recovery_timeout:
                raise CircuitBreakerOpenError(self._policy.recovery_timeout - elapsed)
            self._state = "half-open"
            self._half_open_calls = 0

        if self._state == "half-open":
            if self._half_open_calls >= self._policy.half_open_max_calls:
                raise CircuitBreakerOpenError(0.0)
            self._half_open_calls += 1

    def after_response(self, response: Response, *, now: float) -> None:
        """Update breaker state based on a response."""
        if response.status_code in self._policy.failure_status_codes:
            self.record_failure(now=now)
            return
        self.record_success()

    def after_exception(self, exc: BaseException, *, now: float) -> None:
        """Update breaker state based on an exception."""
        should_count = self._policy.count_network_errors and (
            self._policy.failure_exception_classifier(exc)
        )
        if should_count:
            self.record_failure(now=now)

    def record_success(self) -> None:
        """Record a successful call."""
        self._failure_count = 0
        if self._state == "half-open":
            self._state = "closed"
            self._half_open_calls = 0

    def record_failure(self, *, now: float) -> None:
        """Record a failed call and transition state when needed."""
        if self._state == "half-open":
            self._state = "open"
            self._opened_at = now
            self._failure_count = 0
            self._half_open_calls = 0
            return

        self._failure_count += 1
        if self._failure_count >= self._policy.failure_threshold:
            self._state = "open"
            self._opened_at = now
            self._failure_count = 0


class CircuitBreakerMiddleware(SyncMiddleware):
    """Sync circuit breaker middleware.

    Opens after a configurable number of failures and short-circuits requests
    until the recovery timeout has elapsed.
    """

    def __init__(self, policy: CircuitBreakerPolicy) -> None:
        """Initialize CircuitBreakerMiddleware."""
        self._state = _CircuitBreakerState(policy)
        self._lock = threading.Lock()

    def handle(
        self,
        request: Request,
        next_handler: Callable[[Request], Response],
    ) -> Response:
        """Process a request through the circuit breaker."""
        now = time.monotonic()
        with self._lock:
            self._state.before_call(now=now)

        try:
            response = next_handler(request)
        except Exception as exc:
            with self._lock:
                self._state.after_exception(exc, now=time.monotonic())
            raise

        with self._lock:
            self._state.after_response(response, now=time.monotonic())
        return response


class AsyncCircuitBreakerMiddleware(AsyncMiddleware):
    """Async circuit breaker middleware.

    Async counterpart of ``CircuitBreakerMiddleware``.
    """

    def __init__(self, policy: CircuitBreakerPolicy) -> None:
        """Initialize AsyncCircuitBreakerMiddleware."""
        self._state = _CircuitBreakerState(policy)
        self._lock = asyncio.Lock()

    async def handle(
        self,
        request: Request,
        next_handler: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Process a request through the async circuit breaker."""
        async with self._lock:
            self._state.before_call(now=time.monotonic())

        try:
            response = await next_handler(request)
        except Exception as exc:
            async with self._lock:
                self._state.after_exception(exc, now=time.monotonic())
            raise

        async with self._lock:
            self._state.after_response(response, now=time.monotonic())
        return response
