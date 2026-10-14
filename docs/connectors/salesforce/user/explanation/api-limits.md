# API limits and quota model explained

This article explains how Salesforce enforces API call limits, why a
sliding-window rate limiter is the wrong tool for Salesforce integrations,
and how to observe your quota usage with Plynt.

## Salesforce's 24-hour rolling window

Salesforce enforces a **daily API call limit** that resets on a 24-hour
rolling basis. The limit is calculated as a multiple of your org's edition
and the number of user licenses:

- Enterprise Edition: 1,000 calls per user per day (minimum 1,000,000)
- Unlimited Edition: 5,000 calls per user per day (minimum 5,000,000)

There is no per-second or per-minute rate limit for standard REST API calls.
Salesforce does not throttle burst traffic within a single minute — it only
enforces the daily total.

## What happens when you exceed the quota

When your daily quota is exhausted, Salesforce returns:

```text
HTTP 403 Forbidden
[{"message":"REQUEST_LIMIT_EXCEEDED","errorCode":"REQUEST_LIMIT_EXCEEDED"}]
```

Note the HTTP 403 status code. Salesforce does **not** return 429 Too Many
Requests for quota exhaustion. The 403 response body identifies the error
with the `REQUEST_LIMIT_EXCEEDED` error code.

## Why `RateLimitMiddleware` does not help

Plynt's `RateLimitMiddleware` implements a **sliding window** algorithm
measured in seconds. It is designed to prevent your application from making
more than N requests within a short time window — for example, 10 requests
per second to a downstream API that enforces per-second limits.

This does not model Salesforce's limit at all:

- Salesforce limits operate over 24 hours, not seconds.
- Salesforce does not enforce any burst limit per second.
- Knowing that you've made 5 calls in the last second tells you nothing
  about whether you'll exceed the daily quota.

Using `RateLimitMiddleware` with a Salesforce integration would add
unnecessary latency and still not protect against quota exhaustion.

## The correct approach: observability and circuit breaking

Rather than trying to govern the rate client-side, use the observability
tools Plynt provides:

1. **Observe quota per call** using the `Sforce-Limit-Info` response header,
   which is parsed into `SalesforceApiUsage`:

   ```python
   limits_resp = sf.utility().limits()
   if usage := limits_resp.api_usage:
       if usage.used / usage.limit > 0.80:
           logger.warning("Salesforce API quota at %.0f%%", usage.used / usage.limit * 100)
   ```

1. **Poll org-level limits** using `utility().limits()` (from `GET /limits`)
   when you need detail beyond the request-level counter:

   ```python
   limits_resp = sf.utility().limits()
   daily = limits_resp["DailyApiRequests"]
   # remaining is the quota still available
   ```

1. **Protect against downtime with a circuit breaker** — add
   `CircuitBreakerMiddleware` configured for 500 and 503 status codes.
   See [Add resilience to your Salesforce integration](../how-to/resilience.md).

## Bulk API quota

Bulk API 2.0 jobs consume a separate quota (`DailyBulkV2QueryJobs`), not
the general REST API quota. If you have a large-scale data integration,
prefer the Bulk API to avoid exhausting the general quota.

## Key takeaways

- Salesforce limits are daily, not per-second — `RateLimitMiddleware` is not applicable.
- Quota exhaustion returns HTTP 403 with `REQUEST_LIMIT_EXCEEDED`, not 429.
- Use `SalesforceApiUsage` and `SalesforceLimitsResponse` for observability.
- Use `CircuitBreakerMiddleware` for resilience against transient errors.
- Use the Bulk API for high-volume data operations.
