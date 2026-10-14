# ADR-0020: Rate Limit Middleware

## Status

Accepted

## Context

External APIs frequently enforce rate limits to protect their infrastructure
and ensure fair resource allocation. Rate limits are typically expressed as
a maximum number of requests per time window (e.g. "100 requests per minute").

When a client exceeds a rate limit, the API responds with a rate-limit error
(usually `429 Too Many Requests`) or connection throttling. A naive client
that keeps retrying immediately can worsen the situation by consuming rate
limit quota faster.

The **rate limiting middleware pattern** allows a client to:

- **Track** request counts within a time window.
- **Reject** requests proactively when the limit is approaching.
- **Implement** backoff strategies before requests are sent to the API.

Without dedicated rate limit middleware, applications must implement their
own tracking logic, leading to inconsistent behaviour and duplicated code.
A middleware-based approach ensures consistent, reusable rate limiting
across all transports and services.

## Decision

### Interface

`RateLimitPolicy` (`plynt.base.policies`) controls rate limiting behavior:

```python
from dataclasses import dataclass


@dataclass
class RateLimitPolicy:
    max_requests: int = 100  # requests per window
    window_seconds: float = 60.0  # window duration
```

`RateLimitMiddleware` and `AsyncRateLimitMiddleware` accept a `RateLimitPolicy`
and enforce request throttling:

```python
from plynt.middleware.rate_limit import RateLimitMiddleware
from plynt.base.policies import RateLimitPolicy

transport = HttpxSyncTransport(
    middlewares=[
        RateLimitMiddleware(RateLimitPolicy(max_requests=100, window_seconds=60.0))
    ]
)
```

### Algorithm: Sliding-window counter

The middleware uses a **sliding-window counter** to track request timestamps:

1. For each request, remove all timestamps older than `window_seconds`.
1. If the count of remaining timestamps equals `max_requests`, reject the
   request with `RateLimitExceededError`.
1. Otherwise, record the current timestamp and allow the request.

This approach is:

- **Simple** — no complex state or bucketing.
- **Accurate** — enforces the limit to the second (not bucketed).
- **Per-transport instance** — each middleware instance tracks independently.

**Note:** Rate limit state is **per middleware instance** and does not
synchronize across processes. For distributed rate limiting (cross-process
or cross-service), use the API's rate limit headers (e.g. `X-RateLimit-*`)
to adjust the policy dynamically.

### Module location

`RateLimitMiddleware`, `AsyncRateLimitMiddleware`, and `RateLimitExceededError`
live in `plynt.middleware.rate_limit` and are exported from
`plynt.middleware`.

`RateLimitPolicy` lives in `plynt.base.policies`.

No new dependencies are introduced. This is a Tier 1 core addition.

### Position in the chain

The standard chain order (ADR-0013) is extended:

```text
HeaderMiddleware → AuthMiddleware → CacheMiddleware → CircuitBreakerMiddleware
  → RateLimitMiddleware → RetryMiddleware → _send_once
```

Placing `RateLimitMiddleware` **after** `CircuitBreakerMiddleware` ensures:

- Rate limit checks happen after circuit breaker fast-fail.
- Both rejection types are visible to callers.

Placing it **before** `RetryMiddleware` ensures:

- Retries consume rate limit slots (each attempt counts toward the limit).
- Retry backoff is independent of rate limit enforcement.

Placing it **after** `CacheMiddleware` ensures:

- Successful cached responses do not consume rate limit quota.
- The rate limit is enforced only for requests that hit the network.

### Exception type: `RateLimitExceededError`

When the limit is reached, `RateLimitExceededError` is raised:

```python
class RateLimitExceededError(RuntimeError):
    def __init__(self, retry_after_seconds: float) -> None:
        self.retry_after_seconds = max(0.0, retry_after_seconds)
        super().__init__(
            f"Rate limit exceeded. Retry after {self.retry_after_seconds:.3f}s."
        )
```

This exception provides the calculated wait time for the next available slot.

### Per-instance vs global rate limit

This middleware enforces rate limits **per middleware instance**. If you need
a **global rate limit** shared across multiple transports or services in a
single process, instantiate a single middleware and reuse it:

```python
shared_limiter = RateLimitMiddleware(RateLimitPolicy(max_requests=100))

transport1 = HttpxSyncTransport(middlewares=[shared_limiter, ...])
transport2 = HttpxSyncTransport(middlewares=[shared_limiter, ...])
```

For **cross-process** rate limiting, use the API's rate limit response headers
to adjust the policy dynamically or use an external rate limit service.

## Consequences

- Callers no longer need to implement their own rate limit tracking.
- Requests are rejected proactively before hitting the API, reducing wasted
  bandwidth and quota.
- The ADR-0013 chain is extended with rate limiter placement.
- Rate limit state is scoped to a middleware instance (process-local).
