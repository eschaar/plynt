# Idea: Middleware Extensions

**Status:** Idea — open items only. Items that have been accepted and
implemented are listed below and then removed from this file.

| Item                                         | ADR                                          | Status                                                                      |
| -------------------------------------------- | -------------------------------------------- | --------------------------------------------------------------------------- |
| `HeaderMiddleware` / `AsyncHeaderMiddleware` | [ADR-0015](../adr/0015-header-middleware.md) | Implemented                                                                 |
| `Request.timeout` per-request override       | ADR-0005-A1                                  | Implemented                                                                 |
| `TracingMiddleware` (`plynth[otel]`)         | [ADR-0014](../adr/0014-logging.md)           | Out of scope — `opentelemetry-instrumentation-httpx` covers the common case |
| `MetricsMiddleware` (`plynth[prometheus]`)   | [ADR-0014](../adr/0014-logging.md)           | Out of scope — OTel + Prometheus exporter covers the common case            |

Convert individual items to ADRs when the approach is agreed and
implementation is about to begin.

______________________________________________________________________

## Goal

Extend the core middleware chain (ADR-0013) with additional cross-cutting
concerns that are commonly needed by API client libraries. All middleware
follows the existing `handle(request, next_handler)` contract and is
installed via the `middlewares=` argument on the transport.

Items are grouped into three tiers based on dependency impact:

- **Tier 1 — Core (no new dependencies):** can be added to `plynth.middleware`
  directly.
- **Tier 3 — Test/dev only:** not for production use.

______________________________________________________________________

## Tier 1 — Core middleware

### `CircuitBreakerMiddleware`

**Problem:** `RetryMiddleware` retries on transient failures. When an
upstream is structurally unavailable (e.g. 503 for minutes), retry storms
waste resources and may worsen the upstream's recovery. A circuit breaker
stops attempts fast when failure rate exceeds a threshold, and
automatically re-evaluates after a cooldown period.

**Interface sketch:**

```python
from plynth.middleware.circuit_breaker import CircuitBreakerMiddleware

transport = HttpxSyncTransport(middlewares=[
    CircuitBreakerMiddleware(
        failure_threshold=5,
        recovery_timeout=60.0,
    ),
])
```

**States:** `CLOSED` (normal) → `OPEN` (failing fast) → `HALF_OPEN`
(probing recovery) → `CLOSED`.

**Notes:**

- Complements `RetryMiddleware`; typically placed before retry in the chain
  so the circuit breaker sees logical outcomes, not individual attempts.
- State is per-middleware instance (not shared across processes unless an
  external store is wired in — that is out of scope for the core
  implementation).
- No new dependency required for a basic in-memory implementation.
- Requires a new ADR.

______________________________________________________________________

### `RateLimitMiddleware`

**Problem:** Client-side rate limiting prevents exceeding upstream API
quotas. Without it, callers must implement their own throttle logic per
service.

**Interface sketch:**

```python
from plynth.middleware.rate_limit import RateLimitMiddleware

transport = HttpxSyncTransport(middlewares=[
    RateLimitMiddleware(requests_per_second=10.0),
])
```

**Notes:**

- Token-bucket algorithm is the standard approach: simple, burst-tolerant,
  easy to reason about.
- Sync and async variants both needed; async variant should use
  `asyncio.sleep` rather than `time.sleep`.
- State is per-middleware instance (in-process only).
- No new dependency for a pure Python implementation.
- Requires a new ADR.

______________________________________________________________________

## Tier 3 — Test/dev

### `MockMiddleware`

**Problem:** Tests that use plynth today must either mock httpx at the
transport level or spin up a real server. A `MockMiddleware` that intercepts
requests and returns pre-configured responses would make unit tests simpler
and faster.

**Interface sketch:**

```python
from plynth.middleware.mock import MockMiddleware

mock = MockMiddleware()
mock.register("GET", "/users/1", status=200, json={"id": 1})

transport = HttpxSyncTransport(middlewares=[mock])
```

**Notes:**

- Intended for test environments only — not for production use.
- Raises `AssertionError` for unregistered routes (strict mode) or returns
  404 by default (loose mode).
- Could replace httpx's own `MockTransport` with a middleware-level
  alternative, keeping tests closer to real transport behaviour.
- No new runtime dependency (test-only; `pytest` is already a dev
  dependency).

______________________________________________________________________

## Relation to existing architecture

All Tier 1 items extend `plynth.middleware` directly and follow the
`SyncMiddleware` / `AsyncMiddleware` Protocols from ADR-0013. None requires
changes to `BaseSyncTransport` / `BaseAsyncTransport` or any existing
abstraction.

______________________________________________________________________

## Prerequisites

- ADR-0013 (Transport Base Class + Middleware Chain) must remain stable.
- Each Tier 1 item should be covered by either an amendment to an existing
  ADR or a new one before implementation begins.
