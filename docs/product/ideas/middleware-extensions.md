# Idea: Middleware Extensions

**Status:** Idea-stage items plus a status summary for recently closed
middleware proposals.

| Item                                                         | ADR                                                                   | Status                                                                      |
| ------------------------------------------------------------ | --------------------------------------------------------------------- | --------------------------------------------------------------------------- |
| `HeaderMiddleware` / `AsyncHeaderMiddleware`                 | [ADR-0015](../../architecture/adr/0015-header-middleware.md)          | Implemented                                                                 |
| `Request.timeout` per-request override                       | ADR-0005-A1                                                           | Implemented                                                                 |
| `CircuitBreakerMiddleware` / `AsyncCircuitBreakerMiddleware` | [ADR-0019](../../architecture/adr/0019-circuit-breaker-middleware.md) | Implemented                                                                 |
| `RateLimitMiddleware` / `AsyncRateLimitMiddleware`           | [ADR-0020](../../architecture/adr/0020-rate-limit-middleware.md)      | Implemented                                                                 |
| `TracingMiddleware` (`plynth[otel]`)                         | [ADR-0014](../../architecture/adr/0014-logging.md)                    | Out of scope — `opentelemetry-instrumentation-httpx` covers the common case |
| `MetricsMiddleware` (`plynth[prometheus]`)                   | [ADR-0014](../../architecture/adr/0014-logging.md)                    | Out of scope — OTel + Prometheus exporter covers the common case            |

Convert remaining idea-stage items to ADRs when the approach is agreed and
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

## Remaining idea-stage middleware

No Tier 1 core middleware remains in idea stage.

`CircuitBreakerMiddleware` (ADR-0019) and `RateLimitMiddleware` (ADR-0020)
have both been implemented in sync and async form. The remaining open item in
this document is test/dev oriented.

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
- Any future Tier 1 item should be covered by either an amendment to an
  existing ADR or a new one before implementation begins.
