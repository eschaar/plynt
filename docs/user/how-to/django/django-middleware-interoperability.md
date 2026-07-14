# Django middleware interoperability contract

This guide defines a practical contract between Django/DRF middleware and
outbound plynth calls.

Use this as the baseline integration profile for production services.

## Required integrations

1. Correlation and tracing continuity

   Forward these headers from inbound request to outbound plynth calls:

   1. `X-Request-Id`
   1. `X-Correlation-Id`
   1. `traceparent`
   1. `tracestate`

   In DRF, set `request_headers = RequestHeadersConfig(enabled=True)` on
   `PlynthServiceMixin`.

1. Auth and tenant context propagation

   If ingress middleware enriches request context (tenant, org, user), map only
   explicit values to outbound headers using `request_headers.mapping`.

   Avoid forwarding broad request metadata by default.

1. Cache boundary clarity

   Keep inbound Django response caching and outbound plynth response caching
   separate:

   1. Django cache middleware: cache your API responses.
   1. plynth cache middleware: cache upstream dependency responses.

   Use separate cache aliases and explicit TTLs.

1. Exception mapping safety

   Configure DRF with:

   ```python
   REST_FRAMEWORK = {
       "EXCEPTION_HANDLER": "plynth.adapters.django.drf.errors.plynth_exception_handler",
   }
   ```

   This keeps external payloads stable and avoids leaking internal details.

1. Logging field alignment

   Ensure inbound and outbound logs include shared correlation fields, so one
   request is traceable across service boundaries.

## Optional and non-goals

1. Session coupling

   Do not couple plynth transport behavior to Django sessions unless product
   requirements explicitly need session-derived outbound context.

1. CSRF coupling

   CSRF middleware protects browser-facing endpoints. It is not an outbound
   dependency concern and should not affect plynth transport wiring.

## Recommended implementation checklist

1. Use `PlynthServiceMixin` with `request_headers = RequestHeadersConfig(...)`.
1. Define `request_headers.mapping` for tenant/auth context when needed.
1. Configure dedicated cache aliases for response and auth token caches.
1. Configure `plynth_exception_handler` in DRF settings.
1. Validate with adapter tests and smoke tests in CI.

## Related guides

- [Use DRF service mixin](../drf/use-drf-plynth-service-mixin.md)
- [Use Django transport helper](use-django-transport-helper.md)
- [Use Django cache backend](use-django-cache-backend.md)
