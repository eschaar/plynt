# ADR-0025: Django Adapter Sync and Async Strategy

## Status

Accepted

## Context

ADR-0024 established Django as the first framework adapter for plynt. Since
then, the core transport, client, service, middleware, and connector layers
have continued to preserve sync and async symmetry. That symmetry is explicit in
ADR-0006, ADR-0008, ADR-0009, ADR-0010, ADR-0011, ADR-0012, ADR-0014,
ADR-0015, ADR-0019, and ADR-0020.

The current Django adapter does not yet preserve that symmetry. The shipped
surface is sync-only:

- `transport_from_django_settings()` builds `HttpxSyncTransport`
- `PlyntServiceMixin` composes `SyncMiddleware`
- DRF integration examples and tests assume sync `APIView` handlers

This creates an architectural mismatch. Plynt can speak to async backends,
including Salesforce through the async transport path, but the Django adapter
currently forces framework consumers back onto the sync path.

Django itself supports async views under ASGI and documents a fully async-capable
request stack when middleware and called code are also async-safe. Django also
documents the cost of sync/async adaptation and warns that synchronous
middleware between ASGI and an async view reduces in-process concurrency.

DRF is a weaker foundation for first-class async than Django itself. The DRF
documentation for `APIView` and `GenericAPIView` remains dispatch- and policy-
oriented around synchronous lifecycle methods. The generic view layer is also
heavily documented around ORM-style `queryset` flows, which is not a good fit
for plynt's non-ORM backend integration use cases. That does not make async
DRF impossible, but it does mean the adapter must be deliberate about scope and
must avoid over-promising parity across all DRF abstractions.

## Decision

Plynt will extend the Django adapter strategy to support both sync and async
execution paths.

The strategy is:

1. Keep sync and async as adapter and transport concerns, not business-logic
   concerns.
1. Add async Django transport helpers that mirror the existing sync helper API
   and configuration model.
1. Add an async Django adapter surface that preserves naming and configuration
   parity with the sync surface wherever practical.
1. Treat DRF async support as staged and scope-limited.
1. Support async DRF first for `APIView`-style integrations with explicit async
   handlers and async plynt services.
1. Defer first-class async support for DRF generic views, mixins, and viewsets
   until direct runtime validation proves that the execution path is reliably
   async-safe and worth the maintenance cost.

## Alternatives Considered

### Option A: Keep the Django adapter sync-only

**Pros:**

- Smallest implementation surface.
- Lowest immediate maintenance cost.
- Matches the current adapter implementation and tests.

**Cons:**

- Breaks sync/async symmetry at the framework boundary.
- Forces async-capable connectors back through sync views.
- Makes `httpx2` async support less useful for Django consumers.

**Why rejected:** This would make the framework adapter the point where plynt's
execution-model symmetry stops being consumable.

### Option B: Add async support only through sync/async bridge wrappers

**Pros:**

- Allows some async backend usage without a dedicated async adapter surface.
- Can be introduced incrementally.

**Cons:**

- Encourages `sync_to_async()` and `async_to_sync()` crossings in the hot path.
- Makes runtime behavior harder to reason about and test.
- Reduces or removes the concurrency benefits of an async stack.
- Increases the risk of event-loop misuse in framework code.

**Why rejected:** Bridge wrappers are valid escape hatches, not the primary
adapter design.

### Option C: Add sync and async adapter paths, but limit initial async DRF scope

**Pros:**

- Preserves plynt's execution-model symmetry.
- Keeps the core architecture unchanged and framework-agnostic.
- Lets Django ASGI consumers use async upstream I/O correctly.
- Avoids premature commitment to DRF abstractions that remain sync-oriented.

**Cons:**

- Increases adapter surface area and test matrix size.
- Requires explicit naming and packaging discipline.
- Async DRF support will initially be less feature-complete than sync DRF.

**Why chosen:** This is the narrowest strategy that preserves architecture
consistency without claiming more DRF async maturity than the framework surface
currently justifies.

## Rationale

The core library has already paid the design cost of supporting both sync and
async transports. That design is visible all the way up through the client,
service, middleware, streaming, auth, cache, retry, and logging layers. The
Django adapter should not collapse that architecture into a sync-only boundary.

At the same time, Django and DRF should not be treated as equivalent async
platforms. Django's async model is explicit and documented. It supports async
views under ASGI and clearly explains the tradeoffs when sync middleware or
sync-only code remains in the request path. That makes a dedicated async Django
adapter a sound architectural extension.

DRF is more nuanced. Its `APIView` abstraction can still be useful as a thin API
boundary, but the broader DRF surface is built around synchronous dispatch,
policy hooks, serializers, and generic-view patterns that are commonly paired
with the ORM. For plynt's adapter, the safest async strategy is therefore to
start with thin `APIView`-style integration and avoid promising async parity for
generic views and viewsets until those paths are validated in practice.

This decision also aligns with plynt's non-ORM positioning. If a consumer is
using Django or DRF as an API shell over external backends such as Salesforce,
the highest async value comes from concurrent upstream HTTP I/O, not from ORM-
centric abstractions.

## Consequences

### Positive

- Django consumers can use async plynt transports without leaving the adapter
  boundary.
- The adapter strategy remains aligned with plynt's sync/async core design.
- DRF support stays honest about where async maturity is strong and where it is
  still limited.
- The design encourages thin API layers over non-ORM backends.

### Negative / Tradeoffs

- The Django adapter will need parallel sync and async helper surfaces.
- Tests must cover parity across both execution models.
- Documentation must clearly explain which DRF abstractions are async-ready and
  which are not.

### Risks

- Consumers may assume that all DRF abstractions are equally async-safe.
- Bridge code may creep back in if async boundaries are not explicit.
- Packaging and examples could drift toward sync-first again unless parity is
  reviewed continuously.

Mitigations:

- Keep sync and async adapter entry points explicit in naming and docs.
- Start async DRF support with `APIView`-style integrations only.
- Add parity tests for config loading, middleware wiring, and service factories
  across sync and async paths.
- Document bridge wrappers as fallback tools, not preferred architecture.

## Related ADRs

- ADR-0001: Architecture Principles
- ADR-0002: Layered Architecture
- ADR-0003: Dependency Policy
- ADR-0004: Settings and Configuration
- ADR-0006: Transport Layer
- ADR-0008: Client Layer
- ADR-0009: Service Layer
- ADR-0010: Caching
- ADR-0011: Authentication
- ADR-0012: Retry Strategy
- ADR-0014: Logging Strategy
- ADR-0015: Header Middleware
- ADR-0019: Circuit Breaker Middleware
- ADR-0020: Rate Limit Middleware
- ADR-0023: HTTP Transport Backend Migration to httpx2
- ADR-0024: Framework Adapter Strategy
