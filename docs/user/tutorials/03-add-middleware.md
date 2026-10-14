# Add middleware to a transport

This tutorial adds logging, retry, and circuit breaking to the connector
built in [Tutorial 2](02-build-a-connector.md). Start from the wired
transport created there.

## What middleware does

Middleware wraps the transport. Each middleware sees every request before
it is sent and every response (or error) after it returns. Middleware is
applied in order — the first item in the list is **outermost**.

See [Middleware — ordering and the onion model](../explanation/middleware-model.md)
for a conceptual deep-dive.

## Step 1 — Add logging

`LoggingMiddleware` logs every request and response at `INFO` level with
elapsed time.

```python
from plynt.middleware.logging import LoggingMiddleware
from plynt.http.transport import HttpxSyncTransport

transport = HttpxSyncTransport(
    middlewares=[
        LoggingMiddleware(),
    ]
)
```

Enable the logger to see output:

```python
import logging

logging.basicConfig(level=logging.INFO)
# or, more selectively:
logging.getLogger("plynt").setLevel(logging.INFO)
```

Each log line includes the method, URL, status code, and elapsed time in
milliseconds.

## Step 2 — Add retry

`RetryMiddleware` retries requests that fail with transient errors. Use
`HttpRetryPolicy` (from `plynt.http.policies`) to also retry on HTTP
status codes like 503.

```python
from plynt.middleware.retry import RetryMiddleware
from plynt.http.policies import HttpRetryPolicy

retry = RetryMiddleware(
    HttpRetryPolicy(
        max_attempts=3,  # 1 initial + 2 retries
        backoff_initial=0.5,  # 0.5s before second attempt
        backoff_multiplier=2.0,  # 0.5, 1.0, 2.0, …
        backoff_max=10.0,  # cap at 10s
        retryable_status_codes={500, 502, 503, 504},
    )
)
```

Place retry **inside** any auth middleware so that every retry attempt
carries a valid token:

```python
from plynt.http.auth import auth_from_config

auth = auth_from_config(settings.auth) if settings.auth else None
middlewares = []
if auth:
    middlewares.append(auth)
middlewares.append(retry)

transport = HttpxSyncTransport(middlewares=middlewares)
```

## Step 3 — Add circuit breaking

`CircuitBreakerMiddleware` opens the circuit after a configured number of
consecutive failures and stops making requests until the service recovers.

```python
from plynt.middleware.circuit_breaker import CircuitBreakerMiddleware
from plynt.base.policies import CircuitBreakerPolicy

circuit_breaker = CircuitBreakerMiddleware(
    CircuitBreakerPolicy(
        failure_threshold=5,  # open after 5 consecutive failures
        recovery_timeout=30.0,  # probe again after 30 seconds
        failure_status_codes={500, 502, 503, 504},
    )
)
```

## Step 4 — Combine all middleware

The recommended order is: logging → auth → retry → circuit breaker.

```python
import logging
from plynt.http.transport import HttpxSyncTransport
from plynt.http.auth import auth_from_config
from plynt.http.policies import HttpRetryPolicy
from plynt.middleware.logging import LoggingMiddleware
from plynt.middleware.retry import RetryMiddleware
from plynt.middleware.circuit_breaker import CircuitBreakerMiddleware
from plynt.base.policies import CircuitBreakerPolicy

logging.basicConfig(level=logging.INFO)

settings = IssueTrackerSettings()

middlewares = [LoggingMiddleware()]

if settings.auth:
    middlewares.append(auth_from_config(settings.auth))

middlewares += [
    RetryMiddleware(HttpRetryPolicy(max_attempts=3, retryable_status_codes={500, 503})),
    CircuitBreakerMiddleware(
        CircuitBreakerPolicy(
            failure_threshold=5, recovery_timeout=30.0, failure_status_codes={500, 503}
        )
    ),
]

transport = HttpxSyncTransport(middlewares=middlewares)
```

## Step 5 — Handle middleware errors

When the circuit is open, `CircuitBreakerOpenError` is raised without
making a network call. When all retry attempts are exhausted, the last
error from the network is re-raised.

```python
from plynt.middleware.circuit_breaker import CircuitBreakerOpenError

try:
    issues = tracker.issues().list()
except CircuitBreakerOpenError as e:
    print(f"Service unavailable, retry after {e.retry_after_seconds:.0f}s")
```

## Async

Every sync middleware has an async variant. Use `AsyncLoggingMiddleware`,
`AsyncRetryMiddleware`, and `AsyncCircuitBreakerMiddleware` with
`HttpxAsyncTransport`.

## Next steps

- [Add response caching](04-add-caching.md) — add `CacheMiddleware` to
  skip network calls for repeated GET requests.
- [Write custom middleware](../how-to/write-middleware.md) — implement your
  own middleware.
