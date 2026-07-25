# FastAPI Framework Adapter Change Document

status: DONE
type: feature
reference: ROADMAP-4C
last_modified: 2026-07-25

## Goal and Context

Add first-party FastAPI support as `plynth[fastapi]` so FastAPI services can
use plynth transports and clients with idiomatic FastAPI lifecycle and
dependency injection patterns, without repeating manual wiring.

Primary use case:

1. FastAPI services act as API facades over external backends.
1. Plynth is used to call upstream SaaS and internal backend APIs.
1. FastAPI remains the HTTP edge, validation, and response-shaping layer,
   while plynth owns outbound API transport, auth, retry, and middleware
   composition.

Requested outcome:

1. Provide a small, explicit FastAPI adapter surface focused on lifecycle and
   dependency injection.
1. Keep the adapter async-first and aligned with existing `HttpxAsyncTransport`
   behavior.
1. Keep core plynth layers framework-agnostic and avoid dependency leaks.

Explicit non-goals:

1. No FastAPI imports in `plynth.base`, `plynth.http`, or connector modules.
1. No replacement of FastAPI routing, validation, or exception handling.
1. No sync-first abstraction layer for FastAPI; sync support is optional and
   lower priority.

Constraints and dependencies:

1. Follow ADR-0002, ADR-0003, ADR-0004, and ADR-0024.
1. Keep FastAPI-specific code under `src/plynth/adapters/fastapi/`.
1. Introduce the adapter as an optional extra only (`plynth[fastapi]`).
1. Keep implementation aligned with ADR-0026.

## AS-IS

Repository evidence:

1. Django and DRF adapters already exist in `src/plynth/adapters/django/` and
   provide the current framework-adapter baseline.
1. FastAPI scope and ADR context are documented in
   `docs/product/roadmap.md` and
   `docs/architecture/adr/0026-fastapi-adapter-lifecycle-and-di.md`.
1. `HttpxAsyncTransport.from_settings()` already supports typed settings,
   auth wiring, and cache wiring, so FastAPI integration can stay thin.
1. `HTTPSettings` and `ApiSettings` already fit common FastAPI
   `pydantic-settings` usage.

Current behavior summary:

1. Teams can integrate plynth in FastAPI with first-party lifecycle and DI
   helpers.
1. A first-party lifespan helper manages named transports on
   `FastAPI(lifespan=...)`.
1. First-party `Depends` factories resolve named transport, client, and
   service dependencies.
1. Official FastAPI guidance covers request-header propagation, upstream error
   mapping boundaries, and service-factory patterns.

## TO-BE

Add a dedicated FastAPI adapter package under `src/plynth/adapters/fastapi/`
with a minimal, composable API.

### Public adapter surface

1. `PlynthLifespan` (or equivalent factory) to create and close one or more
   named transports during app startup and shutdown.
1. `get_transport(name)` dependency factory for `Depends` usage.
1. `get_client(name, client_class, **kwargs)` dependency factory for
   request-scoped client construction on top of app-scoped transport.
1. `get_service(...)` dependency factory for named service construction with
   optional request-level caching.
1. Helpers for request-header propagation into outbound plynth requests.
1. Helpers for mapping plynth exceptions into FastAPI JSON responses.

### Integration focus

1. Use FastAPI lifespan to own outbound transport lifecycle.
1. Use `Depends` factories to resolve named transports and transport-backed
   clients from `request.app.state`.
1. Keep usage docs centered on API-facade workloads for external backends,
   including generic SaaS-backend integrations.
1. Ensure compatibility with plynth sync and async transport usage patterns.

### Design boundaries

1. Keep adapter responsibilities limited to lifecycle and DI.
1. Keep upstream-domain orchestration in services and connectors, not in the
   framework adapter.
1. Do not duplicate plynth auth, retry, caching, or error-mapping logic in
   the adapter layer.

## Impact (high level)

Architecture and boundaries:

1. Adds a thin FastAPI adapter layer without changing core abstractions.
1. Preserves framework-agnostic core and connector boundaries.

API and model implications:

1. Introduces optional adapter entry points only; no breaking change to
   existing plynth public APIs.
1. No model changes required in `plynth.base` or connector response models.

Security and privacy implications:

1. No credentials in code; all secrets continue through environment or secret
   stores.
1. Header propagation helpers must include denylist handling to avoid
   forwarding sensitive headers by default.
1. Error handling docs must avoid leaking upstream internals.

Operational implications:

1. Standardize startup and shutdown behavior for outbound transports.
1. Reduce socket/resource leak risk by centralizing `close()` and `aclose()`
   behavior.
1. Improve observability consistency when combined with existing logging,
   retry, and circuit-breaker middleware.

## Acceptance Criteria

1. `plynth[fastapi]` installs FastAPI adapter dependencies and exposes public
   FastAPI adapter symbols.
1. A FastAPI app can register one or more named transports via a
   first-party lifespan helper.
1. Route handlers can resolve named transport or client instances through
   `Depends` without manual state plumbing.
1. Route handlers can resolve named services with optional per-request
   caching through `Depends`.
1. Adapter provides framework-native request-header propagation and exception
   mapping helpers.
1. Adapter behavior supports common external-backend facade usage,
   including generic SaaS-backend integration patterns.
1. Adapter tests cover startup, shutdown, dependency resolution,
   missing-name failures, and cleanup guarantees.
1. Docs include one end-to-end FastAPI example with an upstream service call.
1. `make check` remains green with the new extra enabled.

## Test Scenarios

Happy path:

1. App startup creates named transports; routes resolve dependencies and call
   an upstream service through plynth.
1. App shutdown closes all managed transports cleanly.

Failure path:

1. Requesting an unknown transport name returns a clear framework-level error.
1. Lifespan startup failure closes already-created transports before re-raise.
1. Misconfigured settings fail early with actionable validation errors.

Regression path:

1. Existing Django and DRF adapter tests remain green.
1. Existing connector tests (including Salesforce and LLM) remain unaffected.
1. Existing users without the `fastapi` extra are unaffected.

## Verification Evidence

Repository gate executed successfully on 2026-07-25:

1. `ruff format --check src tests`
1. `pre-commit run markdownlint --all-files`
1. `ruff check src tests`
1. `mypy src tests`
1. `pytest` with full suite

Observed result:

1. `1902 passed, 9 skipped, 2 warnings` in full test run.
1. Global coverage result: `TOTAL 98%`.
