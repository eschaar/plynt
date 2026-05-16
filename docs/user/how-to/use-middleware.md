# How to use middleware

Plynth's transport accepts a list of middleware objects that wrap every
outgoing request. Middleware is composable and order-dependent: the first
item in the list is the outermost wrapper.

## Available middleware

| Class                          | Module                              | Purpose                                     |
| ------------------------------ | ----------------------------------- | ------------------------------------------- |
| `CacheMiddleware`              | `plynth.middleware.cache`           | Cache GET responses                         |
| `LoggingMiddleware`            | `plynth.middleware.logging`         | Log request/response metadata               |
| `HeaderMiddleware`             | `plynth.middleware.header`          | Inject static headers on every request      |
| `RetryMiddleware`              | `plynth.middleware.retry`           | Retry on transient failures with backoff    |
| `CircuitBreakerMiddleware`     | `plynth.middleware.circuit_breaker` | Open circuit after repeated failures        |
| `RateLimitMiddleware`          | `plynth.middleware.rate_limit`      | Enforce a max request rate (sliding window) |
| `ThrottleGovernanceMiddleware` | `plynth.middleware.throttle`        | React to upstream throttle signals          |

Async variants (`AsyncCacheMiddleware`, `AsyncLoggingMiddleware`,
`AsyncRetryMiddleware`, etc.) exist for every sync class.

## Add logging

```python
from plynth.middleware.logging import LoggingMiddleware
from plynth.http.transport import HttpxSyncTransport

transport = HttpxSyncTransport(middlewares=[LoggingMiddleware()])
```

## Add retry

```python
from plynth.middleware.retry import RetryMiddleware
from plynth.http.policies import HttpRetryPolicy

transport = HttpxSyncTransport(
    middlewares=[
        RetryMiddleware(
            HttpRetryPolicy(
                max_attempts=3,
                retryable_status_codes={429, 500, 503},
            )
        ),
    ]
)
```

## Add circuit breaking

```python
from plynth.middleware.circuit_breaker import CircuitBreakerMiddleware
from plynth.http.policies import HttpCircuitBreakerPolicy

transport = HttpxSyncTransport(
    middlewares=[
        CircuitBreakerMiddleware(
            HttpCircuitBreakerPolicy(
                failure_threshold=5,
                recovery_timeout=30.0,
                failure_status_codes={500, 503},
            )
        ),
    ]
)
```

## Add static request headers

```python
from plynth.middleware.header import HeaderMiddleware

transport = HttpxSyncTransport(
    middlewares=[
        HeaderMiddleware({"X-Source": "my-service"}),
    ]
)
```

## Add response caching

```python
from plynth.cache import LocMemCache
from plynth.middleware.cache import CacheMiddleware

transport = HttpxSyncTransport(
    middlewares=[CacheMiddleware(LocMemCache(), ttl=300)]
)
```

See [How to use caching](use-cache.md) for backend options.

## Combine middleware

Place `CacheMiddleware` outermost so a cache hit skips everything else.
Place auth between headers and retry. Place `CircuitBreakerMiddleware`
innermost so the breaker trips on failures that exhaust retries:

```python
from plynth.cache import LocMemCache
from plynth.middleware.cache import CacheMiddleware
from plynth.middleware.logging import LoggingMiddleware
from plynth.middleware.header import HeaderMiddleware
from plynth.middleware.retry import RetryMiddleware
from plynth.middleware.circuit_breaker import CircuitBreakerMiddleware
from plynth.http.policies import HttpRetryPolicy, HttpCircuitBreakerPolicy
from plynth.http.auth import auth_from_config, OAuth2ClientCredentialsConfig

auth = auth_from_config(OAuth2ClientCredentialsConfig(...))

middlewares = [
    CacheMiddleware(LocMemCache(), ttl=60),
    LoggingMiddleware(),
    HeaderMiddleware({"X-Source": "my-service"}),
    auth,
    RetryMiddleware(HttpRetryPolicy(max_attempts=3, retryable_status_codes={500, 503})),
    CircuitBreakerMiddleware(
        HttpCircuitBreakerPolicy(failure_threshold=5, recovery_timeout=30.0)
    ),
]

transport = HttpxSyncTransport(middlewares=middlewares)
```

## Rate limiting

Use `RateLimitMiddleware` to prevent exceeding a target API's request
quota from the client side:

```python
from plynth.middleware.rate_limit import RateLimitMiddleware
from plynth.base.policies import RateLimitPolicy

transport = HttpxSyncTransport(
    middlewares=[
        RateLimitMiddleware(
            RateLimitPolicy(max_requests=10, window_seconds=1.0)
        )
    ]
)
```

`RateLimitExceededError` is raised when the limit is hit.

## Upstream throttle governance

Use `ThrottleGovernanceMiddleware` to react to throttle signals returned by
the upstream API (for example `429` or `503` with `Retry-After`).

```python
from plynth.base.policies import ThrottleGovernancePolicy
from plynth.middleware.throttle import ThrottleGovernanceMiddleware

transport = HttpxSyncTransport(
    middlewares=[
        ThrottleGovernanceMiddleware(
            ThrottleGovernancePolicy(
                reject_on_detection=False,
                min_delay_seconds=1.0,
                max_delay_seconds=60.0,
            )
        ),
    ]
)
```

With `RetryMiddleware`, governance delay is respected by retry using
`max(backoff, governance_delay)`.

## Write your own middleware

See [How to write custom middleware](write-middleware.md).

## Reference

Full API for every middleware class and their policy types:
[Middleware reference](../reference/middleware.md).
