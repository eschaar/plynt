# Django Framework Adapter Change Document

status: BUILD
type: feature
reference: ROADMAP-4A
last_modified: 2026-07-15

## Goal and Context

Add first-party Django support as `plynt[django]` so Django services can use
plynt transports, auth, and caching with Django-native configuration and
cache infrastructure instead of hand-written bridging code.

The implementation should make Django integration feel natural in the same
way plynt already feels natural in plain Python: explicit, typed, and thin.
The adapter must help with the places where Django projects repeatedly do
manual work today:

1. reading API client config from Django settings,
1. reusing `django.core.cache` for response and OAuth2 token caching,
1. building a transport without rewriting plynt's middleware wiring by hand,
1. documenting how plynt logging should fit into Django's `LOGGING` config.

Primary use case:

1. The main target is not replacing Django's own HTTP internals.
1. The main target is Django and DRF projects that act as API façades over
   external systems, where request validation, auth, permissions, and response
   shaping live in Django/DRF while upstream business data comes from external
   APIs reached through plynt.
1. This means the adapter family should optimize for external-backend service
   orchestration, not for database-model convenience or generic requests-style
   HTTP usage.

Support model:

1. `plynt[django]` is the first slice and covers Django-core integration.
1. DRF support should be implemented as a second slice on top of the Django
   adapter family, not mixed into the first Django-core release.
1. DRF is therefore not a separate top-level framework adapter peer to
   Django, FastAPI, or Flask. It is a Django-specific sub-adapter with its own
   optional dependency and API surface.

Constraints and dependencies:

1. Follow [ADR-0002](../architecture/adr/0002-layered-architecture.md),
   [ADR-0003](../architecture/adr/0003-dependency-policy.md),
   [ADR-0004](../architecture/adr/0004-settings-and-configuration.md),
   [ADR-0010](../architecture/adr/0010-caching.md), and
   [ADR-0024](../architecture/adr/0024-framework-adapter-strategy.md).
1. Follow [ADR-0025](../architecture/adr/0025-django-adapter-sync-async-strategy.md)
   for approved async Django and async DRF follow-up scope.
1. Keep all Django imports under the framework-adapter boundary.
1. Keep sync and async as explicit adapter concerns and preserve config parity
   between both paths.

## AS-IS

Repository evidence in plynt:

1. `HttpxSyncTransport.from_settings()` and `HttpxAsyncTransport.from_settings()`
   already wire auth and cache behavior from `HTTPSettings`, so framework work
   only needs to bridge into existing settings and cache contracts.
1. `HTTPSettings` already exposes `auth`, `caches`, `default_cache`, and
   `default_auth_cache` extension points that a Django adapter can target.
1. `Response` is already a neutral dataclass with `status_code`, `headers`,
   and `content`, so a Django cache adapter can safely serialize the neutral
   response form rather than framework- or library-specific objects.
1. [docs/product/roadmap.md](../product/roadmap.md) marks Django as the first
   framework adapter and [ADR-0024](../architecture/adr/0024-framework-adapter-strategy.md)
   makes that ordering explicit.
1. Cache backend documentation already promises guidance for wrapping
   framework-native caches behind plynt's cache protocol.

Observed Django service patterns:

1. Django services commonly keep third-party API client configuration inside
   `settings.py` as dict-like config blocks.
1. Django services commonly use a mix of local-memory and `django-redis`
   aliases through `django.core.cache`.
1. Django services commonly enrich logs from the current Django request.
1. Django APIs commonly propagate correlation headers such as `X-Request-Id`
   into downstream service calls.
1. Thread-local request helpers are a recurring Django integration pattern,
   especially when request context must be available outside the view layer.

Current behavior summary:

1. Plynt already works in Django if a consumer writes the wiring manually.
1. There is no first-party Django settings bridge.
1. There is no first-party adapter from `django.core.cache` to plynt's cache
   protocol.
1. There is no first-party helper for building a sync transport from Django
   settings plus Django cache aliases.
1. Logging works today through stdlib compatibility, but there is no
   Django-focused setup guide.
1. Request-context and request-id propagation are useful patterns in the
   reference repos, but they are still application-level concerns rather than
   proven generic adapter requirements.
1. Many Django API projects also use DRF, but plynt does not yet define a
   first-party DRF integration surface.
1. Plynt is strongest in Django and DRF when those frameworks front external
   backends rather than when they simply wrap Django ORM models.

## TO-BE

The Django implementation will add a small, cohesive adapter package under
`src/plynt/adapters/django/`.

### Django versus DRF support

The implementation should be split into two layers:

1. `plynt[django]` for Django-core integration.
1. `plynt[drf]` for DRF-specific integration built on top of the Django-core
   layer.

The DRF layer should live under `src/plynt/adapters/django/drf/`, because it
depends on Django support and should reuse the Django adapter primitives.
It should not be treated as a separate top-level framework adapter.

### Public Django adapter surface

Phase 1 should expose these public entry points:

1. `from_django_settings(name, settings_class, *, settings_obj=None)`
   in `plynt.adapters.django.settings`.
1. `DjangoCacheBackend(alias="default")`
   in `plynt.adapters.django.cache`.
1. `transport_from_django_settings(name, settings_class, *, settings_obj=None,`
   `response_cache_alias=None, auth_cache_alias=None, middlewares=None)`
   in `plynt.adapters.django.transport`.

The package `src/plynt/adapters/django/__init__.py` should re-export these
public names.

### Planned DRF adapter surface

Phase 2 should expose a small DRF-specific surface on top of the Django-core
adapter:

1. `PlyntServiceMixin` in `plynt.adapters.django.drf.views` for `APIView`
   and `ViewSet` classes that need one or more plynt transports or service
   factories.
1. `build_request_header_middleware(request, headers=None)` in
   `plynt.adapters.django.drf.headers` to propagate selected inbound headers
   such as `X-Request-Id` into outbound plynt requests.
1. DRF-focused docs showing integration with `APIView` and `ViewSet`.

The first DRF slice should stay small. It should help with request-aware
service construction and header propagation, but it should not define a
generic upstream-to-DRF exception policy in the first release.

### Approved async follow-up slice

ADR-0025 approves an explicit async follow-up for the Django adapter family.
That slice should preserve naming and configuration symmetry with the sync
adapter and should start with thin `APIView`-style DRF integrations.

The first async slice should expose these public entry points:

1. `async_transport_from_django_settings(name, settings_class, *,`
   `settings_obj=None, response_cache_alias=None, auth_cache_alias=None,`
   `middlewares=None)` in `plynt.adapters.django.transport`.
1. `AsyncPlyntServiceMixin` in `plynt.adapters.django.drf.views` for async
   `APIView` handlers that need one or more async plynt transports or service
   factories.
1. `build_async_request_header_middleware(request, headers=None, *,`
   `deny_headers=None)` in `plynt.adapters.django.drf.headers` to build
   `AsyncHeaderMiddleware` with the same denylist and mapping semantics as the
   sync helper.

The async slice should reuse these existing config objects rather than create
async-specific variants:

1. `CacheAliasesConfig`
1. `RequestHeadersConfig`

Sync and async entry points should stay explicit. The adapter should not try to
auto-detect execution mode or hide sync versus async service construction.

### Async DRF scope and non-goals

The first async DRF slice should be intentionally narrow.

In scope:

1. async `APIView` method handlers such as `async def get(...)`
1. async plynt service factories returning clients or services backed by
   `HttpxAsyncTransport`
1. async request-header propagation using `AsyncHeaderMiddleware`
1. smoke tests that prove one async request path works with adapter-managed
   transport and service caching

Out of scope for the first async slice:

1. DRF generic views built around queryset and ORM assumptions
1. async support claims for DRF mixins and viewsets
1. sync-to-async bridge wrappers as the main integration strategy
1. adapter-level abstraction that hides whether a consumer is using sync or
   async plynt services

### External-backend API layer support

The Django and DRF adapter family should explicitly support the "API façade
over external backends" pattern.

This means Phase 1 and Phase 2 should make these workflows easy:

1. validate and normalize inbound request data with Django or DRF,
1. build a typed plynt settings object from framework config,
1. call one or more external APIs through plynt services or transports,
1. propagate correlation headers into outbound calls when needed,
1. shape the final response in Django or DRF without introducing framework
   concerns into plynt core layers.

The adapter family should not try to turn plynt into a replacement for
`requests` usage inside Django internals. It should focus on higher-level,
typed external-service access from Django and DRF applications.

### Settings bridge

`from_django_settings(...)` will:

1. read a named value from `django.conf.settings` or a supplied settings-like
   object,
1. require that value to be a mapping,
1. normalize common Django-style uppercase keys to the lowercase field names
   expected by plynt settings classes,
1. instantiate the requested `HTTPSettings` or `ApiSettings` subclass,
1. return a typed settings instance ready for plynt transport construction.

This keeps Django knowledge out of core settings subclasses while allowing a
Django project to keep service configuration inside `settings.py`.

### Cache bridge

`DjangoCacheBackend` will wrap `django.core.cache.caches[alias]` and satisfy
the plynt `CacheBackend` protocol:

1. `get()` reads one cache key and returns a deserialized neutral value.
1. `set(..., ttl=...)` writes through to Django's cache backend using
   `timeout=ttl`.
1. `delete()` and `clear()` delegate to the Django cache backend.
1. response payloads are serialized as explicit dictionaries containing a
   schema version, status code, headers, and raw content.

The adapter will not use pickle for cached `Response` values. The stored form
must stay explicit, versionable, and safe across deploys.

### Transport wiring helper

`transport_from_django_settings(...)` will provide the missing high-level
Django integration step:

1. load a typed plynt settings object through `from_django_settings(...)`,
1. construct a sync `HttpxSyncTransport`,
1. wire auth exactly the same way as `HttpxSyncTransport.from_settings()`,
1. resolve `response_cache_alias` and `auth_cache_alias` to
   `DjangoCacheBackend` instances,
1. attach those backends to the same middleware and token-cache positions that
   plynt uses for its built-in cache backends.

This helper is necessary because Django cache aliases are runtime objects, not
static `CacheConfig` dataclasses.

### Internal implementation support

To avoid duplicating too much of `HttpxSyncTransport.from_settings()` inside
the Django adapter, the implementation may extract a small internal helper in
`plynt.http.transport` for middleware assembly from a typed settings object.
That refactor must remain behavior-preserving and must not add Django imports
to the core.

### Documentation surface

Phase 1 documentation will add a Django-focused guide that shows:

1. how to keep plynt service config in Django settings,
1. how to build a settings object via `from_django_settings(...)`,
1. how to build a transport with Django response and token caches,
1. how to use plynt's existing logging filters in Django `LOGGING`.

### Work packages

Implementation should be executed as these work packages:

#### WP1. Django packaging and public boundary

1. Add the `plynt[django]` optional extra.
1. Create `src/plynt/adapters/django/` with stable public re-exports.
1. Add import-boundary tests proving Django imports do not leak into core.

#### WP2. Django settings bridge

1. Implement `from_django_settings(...)`.
1. Normalize Django-style setting keys into plynt settings field names.
1. Add focused tests for valid payloads, missing setting names, and invalid
   mapping shapes.

#### WP3. Django cache bridge

1. Implement `DjangoCacheBackend`.
1. Add explicit serialization format for neutral `Response` objects.
1. Add focused tests for read, write, delete, clear, TTL, and corrupt payload
   fallback behavior.

#### WP4. Django transport helper

1. Implement `transport_from_django_settings(...)`.
1. Reuse the same auth and cache semantics as plynt settings-driven wiring.
1. Extract a small internal helper in `plynt.http.transport` only if that is
   the cleanest way to avoid logic duplication.
1. Add focused tests for response-cache alias wiring and auth-token cache
   alias wiring.

#### WP5. Django documentation and examples

1. Add one end-to-end Django example for external-backend API usage.
1. Document `settings.py` layout, `CACHES` usage, transport construction, and
   logging integration.

#### WP6. DRF packaging and request-aware integration

1. Add the `plynt[drf]` optional extra on top of `plynt[django]`.
1. Implement `PlyntServiceMixin` for `APIView` and `ViewSet` classes.
1. Implement request-header propagation helpers for correlation and tracing
   headers.
1. Add DRF-focused docs for request validation plus outbound external-backend
   calls through plynt.

#### WP7. DRF ergonomics follow-up

1. Evaluate exception translation from plynt errors to DRF `APIException`.
1. Add test helpers for DRF view tests that rely on adapter-backed services.

#### WP8. Async Django transport helper

1. Add `async_transport_from_django_settings(...)` next to the existing sync
   helper in `plynt.adapters.django.transport`.
1. Mirror the existing settings parsing and cache alias semantics.
1. Build `HttpxAsyncTransport` and wire `async_auth_from_config(...)`,
   `AsyncCacheMiddleware`, and `AsyncRetryMiddleware` in the same canonical
   order as the sync path.
1. Extract or reuse a small internal middleware-assembly helper only if that
   keeps sync and async parity obvious and avoids Django imports leaking into
   core.

#### WP9. Async DRF APIView integration

1. Add `AsyncPlyntServiceMixin` in `plynt.adapters.django.drf.views`.
1. Keep class-level configuration names aligned with `PlyntServiceMixin`:
   `settings_name`, `settings_class`, `cache_aliases`, `middlewares`,
   `service_factories`, and `request_headers`.
1. Provide explicit async methods such as `get_transport()`,
   `get_service_factories()`, `get_service(name)`, and `get_client(name)`.
1. Cache transports and named services per view instance just like the sync
   mixin, but do not share instances across requests.

#### WP10. Async header propagation and parity tests

1. Add `build_async_request_header_middleware(...)` using
   `AsyncHeaderMiddleware`.
1. Keep the same default forwarded header map and sensitive-header denylist as
   the sync helper.
1. Add parity tests that compare sync and async behavior for settings loading,
   response-cache alias wiring, auth-token cache alias wiring, request-header
   propagation configuration, and unknown service-name failures.
1. Add smoke tests for async Django and async DRF `APIView` integration.

### Recommended implementation order for the async slice

Implement the async follow-up in this order:

1. WP8 first, because all async framework integration depends on an async
   transport helper with stable cache and auth semantics.
1. WP10 header helper parity next, because it is small and de-risks the
   request-aware DRF path.
1. WP9 mixin work after the transport and header pieces are already validated.
1. Async documentation and examples only after smoke tests prove the path.

### Other Django and DRF adapter opportunities

These are not part of the first committed scope, but they are realistic and
interesting extensions if plynt adoption in Django APIs grows:

1. Request-scoped service registry:
   a helper that exposes lazily built plynt services on the current Django or
   DRF request to avoid repeated transport construction in one request cycle.
1. Header propagation adapter:
   configurable middleware or helper for forwarding correlation and tracing
   headers such as `X-Request-Id`, `X-Correlation-Id`, and W3C trace headers.
1. External-backend endpoint toolkit for DRF:
   small helpers for the recurring pattern "validate with serializer, call one
   or more plynt services, map upstream errors, return serializer-shaped
   response".
1. Exception translation for DRF:
   a small exception handler that maps plynt errors to DRF `APIException`
   responses when a project wants first-party response shaping.
1. Dependency-style service injection for DRF views:
   a helper that attaches typed plynt services to `APIView` or `ViewSet`
   instances using declarative configuration instead of manual setup in each
   view.
1. Test helpers for Django and DRF:
   fixtures or factories for building adapter-backed transports with dummy
   caches and request headers in unit tests.
1. Admin and health integration:
   optional helpers that surface plynt cache and upstream connectivity state
   in Django admin pages or health endpoints.
1. Request-context accessor:
   a thin helper for projects that already rely on thread-local request
   middleware and want request-aware outbound policies without hard-coding
   Django access inside service code.
1. Async generic-view and viewset support for DRF, but only after direct
   runtime validation shows the execution path is worth maintaining.

### Deferred from Phase 1

These are useful, but they should stay out of the first implementation slice:

1. DRF support,
1. request-context helpers built on thread-local middleware,
1. automatic request-id propagation helpers.

### Backlog after Phase 1

If real demand appears after the core Django adapter ships, the next useful
additions are:

1. Async Django transport and async DRF `APIView` integration under the
   approved ADR-0025 scope.
1. DRF integration under `plynt[drf]`, including `PlyntServiceMixin` and
   request-header propagation helpers.
1. `RequestContextAccessor` for projects that already install thread-local
   middleware,
1. `RequestIdHeaderInjector` for downstream correlation patterns,
1. optional logging enrichment helpers if documentation alone is not enough.

## Impact (high level)

Architecture and boundaries:

1. Adds a new optional framework-adapter surface without changing core layer
   contracts.
1. Keeps Django imports isolated behind the `plynt[django]` extra.
1. Keeps DRF imports isolated behind a separate `plynt[drf]` extra layered on
   top of the Django adapter package.
1. May require a small internal refactor in `plynt.http.transport` to reuse
   existing settings-to-middleware assembly without copying logic.
1. Leaves request-context and DRF-specific concerns out of Phase 1.

API and model implications:

1. Adds a settings factory, a cache backend, and a transport helper for Django
   consumers.
1. Does not change the public API of `HTTPSettings`, `ApiSettings`, or core
   transports.
1. Introduces one explicit cache-serialization format for neutral `Response`
   objects stored in Django caches.
1. Reserves a second adapter surface for DRF-specific view integration rather
   than overloading the Django-core API.
1. Establishes Django and DRF as a first-class façade layer for external API
   integrations built on plynt.

Security and privacy implications:

1. No secrets stored in code or changedoc examples.
1. Django settings bridge must avoid logging secret values during validation
   failures.
1. Cache serialization must avoid persisting internal-only objects beyond the
   response fields needed for plynt cache semantics.

Operational implications:

1. Django projects can reuse existing `CACHES` aliases instead of duplicating
   Redis configuration in plynt-specific settings subclasses.
1. Django projects can use one adapter helper instead of duplicating transport,
   auth, and cache wiring logic per service.
1. Logging integration remains documentation-first in Phase 1, which keeps the
   runtime surface small.
1. The adapter should work for both local-memory and `django-redis` backends,
   reflecting the reference-repo usage patterns.
1. DRF projects will have a clear follow-up slice for request-aware service
   wiring without forcing DRF onto all Django users.
1. Teams using Django or DRF primarily as an external-backend API façade get a
   clearer, more repeatable integration path than direct ad-hoc HTTP usage.

## Acceptance Criteria

1. A Django optional extra exists and installs the Django dependency required
   by the adapter package.
1. Django consumers can load a plynt settings subclass from a named Django
   settings object without hand-copying values.
1. Django consumers can use a `django.core.cache` alias as the response cache
   and as the OAuth2 token cache through plynt's existing cache hooks.
1. Django consumers can build a sync transport from Django settings and cache
   aliases without reimplementing plynt's middleware assembly manually.
1. The Django-core implementation does not require DRF to be installed.
1. The DRF implementation can later be added without redesigning the
   Django-core adapter API.
1. Core packages remain free of Django imports.
1. Documentation shows a complete sync Django wiring example.
1. Focused tests cover happy path, validation failures, and cache round-trip
   behavior.

## Test Scenarios

Happy path:

1. `from_django_settings()` builds an `HTTPSettings` subclass from a named
   Django settings dict.
1. `DjangoCacheBackend` stores and restores a cached response with headers,
   body, status, and TTL.
1. `transport_from_django_settings()` builds a sync transport with the same
   auth and middleware behavior expected from plynt settings-driven wiring.
1. OAuth2 token caching works when `default_auth_cache` points at a
   Django cache alias resolved by the adapter helper.

Failure path:

1. Missing Django settings key raises a clear configuration error.
1. Invalid Django settings payload shape raises a validation error without
   leaking secrets.
1. Unknown cache alias raises a clear adapter error.
1. Corrupt cached response payload fails closed and behaves as a cache miss.

Regression path:

1. Existing non-Django transport wiring tests continue to pass unchanged.
1. Existing cache backend tests continue to pass unchanged.
1. Existing settings-driven auth and cache wiring remain unchanged for
   non-Django consumers.

## References

1. [ADR-0024](../architecture/adr/0024-framework-adapter-strategy.md)
1. [docs/product/roadmap.md](../product/roadmap.md)
