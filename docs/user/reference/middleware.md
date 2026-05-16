# Middleware reference

Plynth middleware implements `SyncMiddleware` or `AsyncMiddleware` from
`plynth.base.middleware`. All middleware is passed as a list to the
transport constructor.

______________________________________________________________________

## CacheMiddleware

**Module:** `plynth.middleware.cache`
**Async variant:** `AsyncCacheMiddleware`

Caches successful `GET` responses. Responses with status ≥ 400 are never
stored. Non-GET requests are always passed through.

```python
CacheMiddleware(backend: CacheBackend, ttl: float | None = None)
```

| Parameter | Type            | Description                                                                                     |
| --------- | --------------- | ----------------------------------------------------------------------------------------------- |
| `backend` | `CacheBackend`  | The cache backend to use                                                                        |
| `ttl`     | `float \| None` | Time-to-live in seconds passed to `backend.set()`. `None` means no expiry (or backend default). |

TTL is passed to `backend.set()` on every write. Whether the backend
honours it depends on the implementation — `LocMemCache` and
`CachetoolsCache(TTLCache(...))` support it; `DummyCache` ignores it.

See [Cache backends reference](cache-backends.md).

______________________________________________________________________

## LoggingMiddleware

**Module:** `plynth.middleware.logging`
**Async variant:** `AsyncLoggingMiddleware`

Logs request method, URL, response status code, and elapsed time.

```python
LoggingMiddleware()
```

See [How to configure logging](../how-to/configure-logging.md).

______________________________________________________________________

## HeaderMiddleware

**Module:** `plynth.middleware.header`
**Async variant:** `AsyncHeaderMiddleware`

Injects static headers on every outgoing request.

```python
HeaderMiddleware(headers: dict[str, str])
```

```python
HeaderMiddleware({"X-Source": "my-service", "Accept-Language": "en"})
```

______________________________________________________________________

## RetryMiddleware

**Module:** `plynth.middleware.retry`
**Async variant:** `AsyncRetryMiddleware`

Retries failed requests with exponential backoff.

```python
RetryMiddleware(policy: RetryPolicy | HttpRetryPolicy)
```

### Policy: `HttpRetryPolicy` (`plynth.http.policies`)

Extends `RetryPolicy` with HTTP status code awareness. Recommended for
HTTP transports.

| Field                    | Type             | Default                     | Description                                |
| ------------------------ | ---------------- | --------------------------- | ------------------------------------------ |
| `max_attempts`           | `int`            | `3`                         | Total attempts including the first         |
| `backoff_initial`        | `float`          | `0.5`                       | Delay in seconds before the second attempt |
| `backoff_multiplier`     | `float`          | `2.0`                       | Multiplier applied each retry              |
| `backoff_max`            | `float`          | `30.0`                      | Upper bound for computed delay             |
| `retry_on_network_error` | `bool`           | `True`                      | Retry on network-level exceptions          |
| `retryable_status_codes` | `frozenset[int]` | `{429, 500, 502, 503, 504}` | HTTP codes that trigger a retry            |

### Policy: `RetryPolicy` (`plynth.base.policies`)

Protocol-agnostic base. Same fields as `HttpRetryPolicy`, but
`retryable_status_codes` defaults to an empty frozenset.

______________________________________________________________________

## CircuitBreakerMiddleware

**Module:** `plynth.middleware.circuit_breaker`
**Async variant:** `AsyncCircuitBreakerMiddleware`

Opens a circuit after repeated failures to prevent cascading errors.

```python
CircuitBreakerMiddleware(policy: CircuitBreakerPolicy)
```

### Policy: `CircuitBreakerPolicy` (`plynth.base.policies`)

| Field                  | Type             | Default       | Description                                     |
| ---------------------- | ---------------- | ------------- | ----------------------------------------------- |
| `failure_threshold`    | `int`            | `5`           | Consecutive failures before opening the circuit |
| `recovery_timeout`     | `float`          | `30.0`        | Seconds before allowing a half-open probe       |
| `half_open_max_calls`  | `int`            | `1`           | Probe calls allowed in half-open state          |
| `failure_status_codes` | `frozenset[int]` | `frozenset()` | HTTP codes that count as failures               |
| `count_network_errors` | `bool`           | `True`        | Whether network exceptions count as failures    |

### CircuitBreakerOpenError

`CircuitBreakerOpenError(retry_after_seconds: float)` — raised when the
circuit is open; `retry_after_seconds` is the estimated wait time before
the next probe.

______________________________________________________________________

## RateLimitMiddleware

**Module:** `plynth.middleware.rate_limit`
**Async variant:** `AsyncRateLimitMiddleware`

Enforces a maximum request rate using a sliding window counter on the
client side.

```python
RateLimitMiddleware(policy: RateLimitPolicy)
```

### Policy: `RateLimitPolicy` (`plynth.base.policies`)

| Field            | Type    | Default | Description                 |
| ---------------- | ------- | ------- | --------------------------- |
| `max_requests`   | `int`   | `100`   | Maximum requests per window |
| `window_seconds` | `float` | `60.0`  | Window duration in seconds  |

### RateLimitExceededError

`RateLimitExceededError(retry_after_seconds: float)` — raised when the
limit is hit.

______________________________________________________________________

## ThrottleGovernanceMiddleware

**Module:** `plynth.middleware.throttle`
**Async variant:** `AsyncThrottleGovernanceMiddleware`

Reacts to throttle or backpressure signals returned by upstream APIs.
Typical signals include `429`, `503` with `Retry-After`, and exhausted
quota headers such as `X-RateLimit-Remaining: 0`.

```python
ThrottleGovernanceMiddleware(policy: ThrottleGovernancePolicy)
```

### Policy: `ThrottleGovernancePolicy` (`plynth.base.policies`)

| Field                 | Type    | Default | Description                                             |
| --------------------- | ------- | ------- | ------------------------------------------------------- |
| `reject_on_detection` | `bool`  | `False` | Reject immediately when a throttle signal is detected   |
| `min_delay_seconds`   | `float` | `0.5`   | Minimum delay used for throttle-governed retry behavior |
| `max_delay_seconds`   | `float` | `60.0`  | Maximum delay clamp for upstream delay hints            |

### ThrottleGovernedError

`ThrottleGovernedError(response, delay_seconds, reason)` — raised when
policy action is reject.

### Retry integration

When paired with `RetryMiddleware`, governance delay metadata is consumed
by retry and applied as `max(backoff, governance_delay)`.

______________________________________________________________________

## Middleware ordering

The first middleware in the list is outermost (wraps everything). The
recommended order for a typical stack is:

```python
middlewares = [
    CacheMiddleware(...),         # outermost — short-circuit on hit
    LoggingMiddleware(),
    HeaderMiddleware({...}),
    auth_middleware,              # from auth_from_config()
    ThrottleGovernanceMiddleware(...),
    RetryMiddleware(...),
    CircuitBreakerMiddleware(...),  # innermost
]
```

See [Middleware model](../explanation/middleware-model.md) for a detailed
explanation of why ordering matters.

______________________________________________________________________

## Write your own middleware

See [How to write custom middleware](../how-to/write-middleware.md).
