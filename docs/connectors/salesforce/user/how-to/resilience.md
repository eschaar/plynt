# How to add resilience to your Salesforce integration

## Circuit breaking against Salesforce downtime

Salesforce occasionally returns 500 or 503 during maintenance windows or
infrastructure incidents. Use `CircuitBreakerMiddleware` to stop hammering
a failing service and give it time to recover.

```python
from plynth.middleware.circuit_breaker import CircuitBreakerMiddleware
from plynth.base.policies import CircuitBreakerPolicy
from plynth.connectors.salesforce.auth import SalesforceClientCredentialsAuthMiddleware
from plynth.connectors.salesforce.client import SalesforceAPIClient
from plynth.http.transport import HttpxSyncTransport

auth = SalesforceClientCredentialsAuthMiddleware(
    client_id=settings.client_id,
    client_secret=settings.client_secret,
    token_url=settings.token_url,
)
transport = HttpxSyncTransport(
    middlewares=[
        CircuitBreakerMiddleware(
            CircuitBreakerPolicy(
                failure_threshold=5,        # open after 5 consecutive failures
                recovery_timeout=30.0,      # probe again after 30 seconds
                failure_status_codes={500, 503},
            )
        ),
        auth,
    ]
)
client = SalesforceAPIClient(auth=auth, transport=transport)
```

> **Do not add 429 to `failure_status_codes`.** Salesforce uses HTTP 403
> with a `REQUEST_LIMIT_EXCEEDED` body for quota errors, not 429. Adding 403
> to the circuit would open the circuit on quota errors, which is not what
> you want.

When the circuit is open, `CircuitBreakerOpenError` is raised immediately
without making a network call:

```python
from plynth.middleware.circuit_breaker import CircuitBreakerOpenError

try:
    result = sf.query().query(soql)
except CircuitBreakerOpenError as e:
    logger.warning("Salesforce circuit open, retry after %.0fs", e.retry_after_seconds)
    raise
```

## Observe quota usage (without governing it)

Salesforce enforces API limits server-side. The connector surfaces quota
data so your application can react — but it never blocks calls proactively.

### Per-call quota from response headers

Every Salesforce response includes a `Sforce-Limit-Info` header. The
connector parses it and attaches it to the `limits()` response:

```python
limits_resp = sf.utility().limits()
if usage := limits_resp.api_usage:
    pct = usage.used / usage.limit * 100
    if pct > 80:
        logger.warning("Salesforce API quota at %.0f%%", pct)
```

`SalesforceApiUsage` has two fields:

| Field   | Description                              |
| ------- | ---------------------------------------- |
| `used`  | Calls made in the current 24-hour window |
| `limit` | Total calls allowed in the org's plan    |

### Full org limits via `GET /limits`

For per-resource quota detail call `utility.limits()` explicitly. This is
one API call itself, so poll at a schedule appropriate for your workload:

```python
limits_resp = sf.utility().limits()
daily = limits_resp["DailyApiRequests"]
print(f"Daily API calls: {daily.remaining} remaining of {daily.max_value}")

# Other useful limit keys:
# DailyBulkV2QueryJobs, DailyGenericStreamingApiEvents, etc.
```

## Combine circuit breaking with retry

For transient errors (connection timeouts, flapping 503s) combine the
circuit breaker with a retry middleware. Place `CircuitBreakerMiddleware`
outside (first in the list) and `RetryMiddleware` inside, so the breaker
counts only the final failure after all retry attempts are exhausted:

```python
from plynth.middleware.retry import RetryMiddleware
from plynth.http.policies import HttpRetryPolicy

transport = HttpxSyncTransport(
    middlewares=[
        CircuitBreakerMiddleware(
            CircuitBreakerPolicy(failure_threshold=5, recovery_timeout=30.0,
                                 failure_status_codes={500, 503})
        ),
        RetryMiddleware(
            HttpRetryPolicy(max_attempts=3, retryable_status_codes={500, 503},
                            backoff_initial=0.5)
        ),
        auth,
    ]
)
```

## Async

```python
from plynth.middleware.circuit_breaker import AsyncCircuitBreakerMiddleware
from plynth.http.transport import HttpxAsyncTransport

transport = HttpxAsyncTransport(
    middlewares=[
        AsyncCircuitBreakerMiddleware(
            CircuitBreakerPolicy(failure_threshold=5, recovery_timeout=30.0,
                                 failure_status_codes={500, 503})
        ),
        async_auth,
    ]
)
```
