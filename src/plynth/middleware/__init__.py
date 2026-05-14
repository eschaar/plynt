"""Protocol-agnostic middleware implementations for Plynth.

This package (``plynth.middleware``) contains concrete middleware that
can be used with any transport — no HTTP or framework coupling.

Available middleware:

- ``plynth.middleware.cache`` — ``CacheMiddleware``, ``AsyncCacheMiddleware``
- ``plynth.middleware.circuit_breaker`` — ``CircuitBreakerMiddleware``,
  ``AsyncCircuitBreakerMiddleware``
- ``plynth.middleware.header`` — ``HeaderMiddleware``, ``AsyncHeaderMiddleware``
- ``plynth.middleware.logging`` — ``LoggingMiddleware``,
  ``AsyncLoggingMiddleware``
- ``plynth.middleware.rate_limit`` — ``RateLimitMiddleware``,
  ``AsyncRateLimitMiddleware``
- ``plynth.middleware.retry`` — ``RetryMiddleware``, ``AsyncRetryMiddleware``

Log filters and formatter live in ``plynth.log``:
``ThrottleLogs``, ``ExceptionInfoFilter``, ``PlynthHTTPFilter``,
``StructuredFormatter``.
"""

from plynth.middleware.cache import AsyncCacheMiddleware, CacheMiddleware
from plynth.middleware.circuit_breaker import (
    AsyncCircuitBreakerMiddleware,
    CircuitBreakerMiddleware,
)
from plynth.middleware.header import AsyncHeaderMiddleware, HeaderMiddleware
from plynth.middleware.logging import AsyncLoggingMiddleware, LoggingMiddleware
from plynth.middleware.rate_limit import (
    AsyncRateLimitMiddleware,
    RateLimitMiddleware,
)
from plynth.middleware.retry import AsyncRetryMiddleware, RetryMiddleware

__all__ = [
    "AsyncCacheMiddleware",
    "AsyncCircuitBreakerMiddleware",
    "AsyncHeaderMiddleware",
    "AsyncLoggingMiddleware",
    "AsyncRateLimitMiddleware",
    "AsyncRetryMiddleware",
    "CacheMiddleware",
    "CircuitBreakerMiddleware",
    "HeaderMiddleware",
    "LoggingMiddleware",
    "RateLimitMiddleware",
    "RetryMiddleware",
]
