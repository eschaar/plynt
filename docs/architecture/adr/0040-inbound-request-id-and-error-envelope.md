# ADR-0040: Inbound Request ID and Error Envelope

**Date:** 2026-11-01
**Status:** Accepted

## Context

Services built on plynt expose inbound APIs through Django, DRF, or
FastAPI and call upstream systems through plynt. Each service currently
implements the same pieces itself:

- accept or generate a request ID for every inbound request,
- propagate it to upstream calls and logs, and echo it on the response,
- render plynt and application errors in one response format.

The DRF and FastAPI adapters already propagate selected inbound headers
to outbound calls and map plynt errors to a fixed `message`/`code`
payload. They do not create a request ID, store it for the duration of a
request, or let the application choose the error format.

[ADR-0024](0024-framework-adapter-strategy.md) requires framework adapters
to stay thin and avoid duplicating core logic. Building this per framework
would duplicate the same validation, context, and formatting rules.

## Decision

We will:

1. Add a framework-agnostic request-context module to the core, without
   new dependencies:
   - a `contextvars`-based current request ID that works for sync code,
     threads started with copied context, and asyncio tasks,
   - validation of incoming IDs (maximum length and an allowed character
     set) with a configurable header name, `X-Request-ID` by default,
   - a pluggable ID generator, `uuid4` hex by default.
1. `HeaderMiddleware` and `AsyncHeaderMiddleware` gain an opt-in option
   that adds the current request ID to outbound requests.
1. Add a logging filter in `plynt.log` that sets `request_id` on records.
1. Add an error-envelope contract in the core: a callable that receives
   the plynt error, the status code, and the request ID and returns a
   JSON-serializable mapping. The default keeps today's
   `message`/`code` payload, so current responses do not change.
1. Framework adapters only wire the core into each framework:
   - Django: middleware that sets and resets the context and echoes the
     header. The DRF exception handler accepts an envelope callable.
   - FastAPI and ASGI: pure ASGI middleware with the same behavior. The
     FastAPI exception mapping accepts an envelope callable.
1. Rejected or missing inbound IDs are replaced by a generated ID. They
   never cause a request to fail.
1. Plynt does not read, change, or normalize trailing-slash behavior.
   Inbound slash handling stays a framework setting of the application
   (Django `APPEND_SLASH`, Starlette `redirect_slashes`), and outbound
   paths stay exactly as each service defines them. The request-ID
   middleware never derives anything from the path, and logs record the
   path as received.
1. The request-ID middleware runs before framework redirects, so slash
   redirects and other early responses also carry the request ID:
   - Django: document placement above `CommonMiddleware` in `MIDDLEWARE`.
   - FastAPI and ASGI: wrapping the app as ASGI middleware places it
     before router redirects by construction.

## Alternatives Considered

### FastAPI-only helpers (original roadmap 4e)

Smaller, but Django services would keep their own copies and the two
adapters would drift. Rejected.

### Thread-local storage

Breaks under asyncio, where many requests share one thread. Rejected.

### Recommend OpenTelemetry trace IDs instead

Trace IDs need an OTel setup and do not cover callers that send their
own request ID. Applications can still pass a trace ID through the
pluggable generator. Not chosen as the only mechanism.

## Rationale

`contextvars` is the standard-library mechanism that works for both
execution models, matching the sync/async principle. One core contract
keeps behavior identical across frameworks, while each adapter stays a
few lines of glue.

## Consequences

### Positive

- One request ID across inbound response, upstream calls, and logs.
- Consistent error responses for plynt and application errors.
- New framework adapters, such as Flask, reuse the same core.

### Negative / Tradeoffs

- New public API surface in the core, the log package, and adapters.
- Applications must install the middleware to get the context.

### Risks

- Context leaking between requests if middleware does not reset the
  variable. Mitigation: reset with the token in a `finally` block and
  test concurrent sync and async requests.
- Header injection through crafted IDs. Mitigation: strict validation
  before use in responses, upstream headers, or logs.
- Log forging and oversized values from client-supplied IDs.
  Mitigation: a maximum length (128 characters by default) and an
  allowed character set of letters, digits, `-`, `_`, `.`, and `:`.
  Invalid values are replaced, never echoed.
- Trusting IDs from untrusted callers. Mitigation: an option to always
  generate a new ID, for services exposed directly to the internet. The
  request ID is a correlation value only and never used for
  authorization or idempotency.
- Context missing in worker threads, for example `run_in_executor` or
  Django `sync_to_async`. Mitigation: document `contextvars.copy_context`
  and test that the ID is visible in Django sync/async views and FastAPI
  sync and async endpoints.
- Missing request ID on slash redirects or other responses produced
  before the view. Mitigation: placement rules above, with Django and
  FastAPI tests that request a path with and without a trailing slash and
  assert the header on both the redirect and the final response.
- Duplicate or conflicting outbound headers when the application also
  forwards the inbound header. Mitigation: the outbound option sets the
  header only when absent, and tests cover both configurations.
- Error envelope callables that raise or leak details. Mitigation: fall
  back to the default envelope when the callable raises, log the failure,
  and never include tracebacks or response bodies in the default.

## Related ADRs

- [ADR-0014](0014-logging.md): logging.
- [ADR-0015](0015-header-middleware.md): header middleware.
- [ADR-0024](0024-framework-adapter-strategy.md): framework adapters.
- [ADR-0025](0025-django-adapter-sync-async-strategy.md): Django adapter.
- [ADR-0026](0026-fastapi-adapter-lifecycle-and-di.md): FastAPI adapter.
