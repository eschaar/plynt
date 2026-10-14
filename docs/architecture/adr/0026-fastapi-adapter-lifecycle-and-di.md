# ADR-0026: FastAPI Adapter Lifecycle and Dependency Strategy

## Status

Accepted

## Context

ADR-0024 established the framework-adapter direction and identified FastAPI as
an adapter candidate after Django validation. Django and DRF delivery has now
validated the adapter packaging boundary, dependency model, and documentation
approach.

FastAPI is a strong fit for plynt when services act as API facades over
external backends. Typical use cases include:

1. exposing SaaS backend operations through a service-owned API contract,
1. composing multiple external and internal backend calls behind one endpoint,
1. orchestrating multiple upstream APIs with one consistent resilience model.

Without a first-party adapter, teams repeat the same framework wiring:

1. startup and shutdown lifecycle for long-lived transports,
1. request-level dependency injection for named transports and clients,
1. app-state conventions for resolving outbound integration resources.

Plynt already supports both sync and async transports. FastAPI also supports
both sync and async handlers. The adapter should preserve that flexibility
without forcing one execution model into all service routes.

## Decision

Plynt will provide a thin FastAPI adapter under `plynt.adapters.fastapi`
with framework-native lifecycle and dependency primitives.

The adapter surface is:

1. `PlyntLifespan` for creating named transports at startup and closing them
   on shutdown.
1. `get_transport(name)` as a `Depends`-compatible dependency factory.
1. `get_client(name, client_class, **kwargs)` as a dependency factory for
   request-scoped client construction from app-scoped transports.
1. `get_service(...)` as a named service dependency factory with optional
   request-level caching.
1. request-header propagation helpers to map inbound FastAPI request headers
   into outbound plynt header middleware.
1. plynt exception-mapping helpers for consistent JSON error responses in
   FastAPI handlers.

Execution-model policy:

1. The adapter supports both sync and async plynt transport objects.
1. Lifecycle cleanup supports both `aclose()` and `close()` conventions.
1. FastAPI route style remains an application decision:
   - async handlers should prefer async clients/transports.
   - sync handlers may use sync clients/transports.

Boundary policy:

1. FastAPI-specific imports remain inside `plynt.adapters.fastapi` only.
1. Core packages (`plynt.base`, `plynt.http`, middleware, connectors) remain
   framework-agnostic.
1. The adapter does not own business orchestration, framework auth policy, or
   framework exception policy.

## Alternatives Considered

### Option A: No FastAPI adapter, keep manual wiring in each service

**Pros:**

- Zero additional package surface.
- No framework-specific maintenance.

**Cons:**

- Repeated boilerplate across services.
- Higher risk of inconsistent lifecycle cleanup and app-state conventions.
- Slower onboarding for FastAPI services that need outbound integrations.

**Why rejected:** Repetition is high and the patterns are stable enough to
standardize with a thin adapter.

### Option B: Async-only adapter

**Pros:**

- Smaller surface.
- Aligns with common FastAPI guidance.

**Cons:**

- Excludes valid sync-handler integrations.
- Conflicts with plynt's deliberate sync and async support strategy.
- Forces migration pressure where teams still operate mixed sync/async stacks.

**Why rejected:** The adapter should preserve plynt transport flexibility and
FastAPI handler flexibility.

### Option C: Full framework abstraction (routing/auth/error mapping)

**Pros:**

- Could reduce more framework code in consumer services.

**Cons:**

- Expands adapter beyond boundary-translation responsibilities.
- Increases coupling to framework internals and project-specific policy.
- Risks leaking framework assumptions into core package expectations.

**Why rejected:** Adapter scope must stay thin and architectural boundaries must
remain explicit.

## Rationale

The highest-value FastAPI integration work is not in changing plynt core. It
is in removing repeated framework glue while keeping plynt transport, auth,
retry, and middleware behavior untouched.

FastAPI's app lifespan and dependency injection model map cleanly to plynt's
transport-centric design:

1. one app owns long-lived outbound transport resources,
1. request handlers resolve named resources predictably,
1. services keep business logic in explicit orchestration layers.

This model is especially strong for facade-style microservices where FastAPI
owns inbound contracts and plynt owns outbound backend communication.

## Consequences

### Positive

- Standard FastAPI wiring for outbound plynt usage becomes reusable.
- Sync and async transport usage remains available to service teams.
- Lifecycle cleanup behavior becomes consistent across FastAPI services.
- SaaS-backend facade scenarios become easier to implement.

### Negative / Tradeoffs

- Adds one more optional adapter surface to maintain.
- Requires FastAPI-specific examples and tests to stay current.

### Risks

- Teams may misuse sync transports in async-heavy handlers.
- Consumers may expect the adapter to provide framework-wide exception policy.

Mitigations:

1. Document sync vs async handler guidance explicitly.
1. Keep adapter API focused on lifecycle and dependency primitives only.
1. Keep business orchestration patterns in user how-to guides, not in adapter
   internals.

## Related ADRs

- ADR-0001: Architecture Principles
- ADR-0002: Layered Architecture
- ADR-0003: Dependency Policy
- ADR-0004: Settings and Configuration
- ADR-0006: Transport Layer
- ADR-0008: Client Layer
- ADR-0009: Service Layer
- ADR-0011: Authentication
- ADR-0012: Retry Strategy
- ADR-0024: Framework Adapter Strategy
- ADR-0025: Django Adapter Sync and Async Strategy
