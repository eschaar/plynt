# How-to guides

How-to guides are **task-oriented**. Each guide helps you complete one
specific goal. They assume you are already familiar with the basics.

## Core Plynth

- [Add authentication](add-authentication.md) — Bearer tokens, Basic auth,
  OAuth2 client credentials, JWT Bearer, and ROPC flows
- [Use middleware](use-middleware.md) — caching, logging, retry, circuit
  breaking, rate limiting, and static headers
- [Write custom middleware](write-middleware.md) — implement the
  `SyncMiddleware` or `AsyncMiddleware` protocol
- [Use caching](use-cache.md) — choose and configure a cache backend
- [Configure logging](configure-logging.md) — structured JSON logging,
  log throttling, and exception filters
- [Handle errors](handle-errors.md) — catch and inspect typed HTTP exceptions
- [Use async](use-async.md) — switch to async/await for concurrent workloads

## Django how-to guides

- [Use Django cache backend](django/use-django-cache-backend.md) — reuse Django
  `CACHES` aliases with `DjangoCacheBackend`
- [Use Django transport helper](django/use-django-transport-helper.md) — build
  a typed plynth transport from Django settings and cache aliases
- [Django middleware interoperability](django/django-middleware-interoperability.md)
  — contract for tracing, auth context, cache boundaries, exception mapping,
  and logging alignment

## DRF how-to guides

- [Use DRF service mixin](drf/use-drf-plynth-service-mixin.md) — build plynth
  services lazily inside APIView and ViewSet classes, with optional request
  header propagation and exception mapping
- [DRF serializer and business-layer patterns](drf/drf-serializer-business-patterns.md)
  — structure serializer-first endpoint contracts with a separate business
  orchestration layer for backend service calls

## FastAPI how-to guides

- [Build a FastAPI service facade](fastapi/use-fastapi-service-facade.md) —
  lifecycle and dependency wiring for outbound SaaS and internal backend
  integrations

## Connector how-to guides

- [Salesforce how-to guides](salesforce/README.md)
