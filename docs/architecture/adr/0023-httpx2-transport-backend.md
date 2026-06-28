# ADR-0023: HTTP Transport Backend Migration to httpx2

## Status

Proposed

## Context

Plynth currently uses `httpx` as the HTTP backend for
`HttpxSyncTransport` and `HttpxAsyncTransport`.

The project `httpx2` is available as a maintained continuation with active
releases and a compatible sync/async client model. Because this repository is
currently private, we can prioritize internal consistency and delivery speed
over broad backward-compatibility constraints.

We still want to avoid unnecessary churn in the plynth-facing API surface.
The existing transport class names are already widely used across this codebase
and documentation.

## Decision

Migrate plynth's HTTP transport backend from `httpx` to `httpx2`.

The migration rules are:

1. Keep the public transport class names unchanged:
   `HttpxSyncTransport` and `HttpxAsyncTransport`.
1. Keep the middleware and service-facing contracts unchanged.
1. Update internal HTTP backend imports and runtime behavior to `httpx2`.
1. Keep migration scope focused on the HTTP transport layer and directly
   affected tests/docs.

## Boundary Note: Transport vs Middleware Responsibilities

To avoid overlap and confusion, plynth keeps a strict separation:

- Connection-level concerns live in the HTTP transport backend:
  protocol (`http2`), connection pooling limits, keep-alive lifecycle,
  redirect limits, proxy/TLS environment usage (`trust_env`).
- Application-level concerns live in middleware:
  retry/backoff policy, throttle governance, rate limiting, circuit breaker,
  header injection, and response caching behavior.

This means the new HTTPX2 client-tuning options do not replace middleware.
They tune connection mechanics, while middleware continues to control
request/response behavior and reliability policy.

## Alternatives Considered

### Option A: Stay on `httpx`

**Pros:**

- No migration effort.
- No test updates required.

**Cons:**

- Misses the active-maintenance path selected for this project.
- Delays inevitable backend refresh work.

### Option B: Migrate to `httpx2` while preserving plynth names

**Pros:**

- Adopts an actively maintained backend.
- Limits churn by preserving plynth's public transport names.
- Keeps migration localized to transport internals.

**Cons:**

- Requires targeted refactor and test updates.
- Requires dependency and docs refresh.

### Option C: Migrate and rename public transport classes

**Pros:**

- Names align exactly with backend package branding.

**Cons:**

- Large code and docs churn for little technical gain.
- No direct reliability improvement from renaming.

**Why rejected:** Renaming does not improve correctness or performance.

## Rationale

Option B gives the best balance: we get a maintained HTTP backend while
preserving a stable plynth-level API shape. The repository's private status
reduces migration risk tolerance constraints, but preserving names still avoids
unnecessary internal churn.

## Consequences

### Positive

- HTTP backend aligns with active upstream maintenance.
- Minimal plynth API disruption.

### Negative / Tradeoffs

- Short-term migration cost in transport implementation and test fixtures.
- Documentation and dependency metadata must be updated consistently.

### Risks

- Subtle behavior differences in timeout, streaming, and low-level transport
  semantics.
- Misconfiguration risk if connection tuning and middleware policy are treated
  as interchangeable knobs.
- Test assumptions tied to `httpx.MockTransport` and `httpx.Response` types.

Mitigations:

- Run full unit and integration test gates.
- Add focused parity checks for streaming and timeout behavior.
- Keep transport and middleware ownership documented and tested separately.
- Keep migration incremental and isolated to HTTP backend wiring.

## Acceptance Criteria

1. HTTP transport implementation imports and uses `httpx2`.
1. Existing plynth transport class names remain unchanged.
1. HTTP transport tests pass after migration updates.
1. Public docs and dependency metadata reference the new backend correctly.
1. Full local quality gate remains green.

## Related ADRs

- ADR-0003: Dependency Policy
- ADR-0006: Transport Layer
- ADR-0013: Transport Base Class
- ADR-0017: Streaming Response Support
