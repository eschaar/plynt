# Django middleware interoperability contract

This guide defines a practical contract between Django/DRF middleware and
outbound plynt calls.

Use this as the baseline integration profile for production services.

## Required integrations

1. Correlation and tracing continuity

   Install [RequestIDMiddleware](use-request-id-middleware.md) before
   `CommonMiddleware` and response-cache middleware. It validates or generates
   the request ID and echoes it on responses, including redirects.

   Enable scoped outbound propagation with `HeaderMiddleware` or
   `AsyncHeaderMiddleware` using `request_id_policy`. An explicitly forwarded
   request-ID header takes precedence over scoped propagation.

   Forward other correlation and tracing headers only when the application
   uses them:

   1. `X-Correlation-Id`
   1. `traceparent`
   1. `tracestate`

   In DRF, set `request_headers = RequestHeadersConfig(enabled=True)` on
   `PlyntServiceMixin`.

1. Auth and tenant context propagation

   If ingress middleware enriches request context (tenant, org, user), map only
   explicit values to outbound headers using `request_headers.mapping`.

   Avoid forwarding broad request metadata by default.

1. Cache boundary clarity

   Keep inbound Django response caching and outbound plynt response caching
   separate:

   1. Django cache middleware: cache your API responses.
   1. plynt cache middleware: cache upstream dependency responses.

   Use separate cache aliases and explicit TTLs.

1. Exception mapping safety

   Configure DRF with:

   ```python
   REST_FRAMEWORK = {
       "EXCEPTION_HANDLER": "plynt.adapters.django.drf.errors.plynt_exception_handler",
   }
   ```

   This keeps external payloads stable and avoids leaking internal details.

1. Logging field alignment

   Ensure inbound and outbound logs include shared correlation fields, so one
   request is traceable across service boundaries.

## Optional and non-goals

1. Session coupling

   Do not couple plynt transport behavior to Django sessions unless product
   requirements explicitly need session-derived outbound context.

1. CSRF coupling

   CSRF middleware protects browser-facing endpoints. It is not an outbound
   dependency concern and should not affect plynt transport wiring.

## Recommended implementation checklist

1. Install request-ID middleware before redirects and response caches.
1. Use `PlyntServiceMixin` with `request_headers = RequestHeadersConfig(...)`.
1. Define `request_headers.mapping` for tenant/auth context when needed.
1. Configure dedicated cache aliases for response and auth token caches.
1. Configure `plynt_exception_handler` in DRF settings.
1. Validate with adapter tests and smoke tests in CI.

## Related guides

- [Use DRF service mixin](drf/use-drf-plynt-service-mixin.md)
- [Use Django transport helper](use-django-transport-helper.md)
- [Use Django cache backend](use-django-cache-backend.md)
