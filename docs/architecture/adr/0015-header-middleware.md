# ADR-0015: Header Middleware

## Status

Accepted

## Context

Many external APIs require a fixed set of headers on every request:
correlation IDs, `User-Agent` strings, tenant identifiers, `Accept-Language`,
or custom API tokens such as `X-Api-Key`. Without dedicated middleware, these
headers must be injected in one of two unsatisfactory ways:

1. **Service-layer repetition** — every service method manually adds headers
   when constructing a `Request`. This scatters infrastructure concerns across
   domain code.
1. **Transport subclassing** — a custom `BaseSyncTransport` subclass overrides
   `_send_once` to add headers. This couples header logic to the I/O layer and
   prevents reuse.

Neither approach fits the chain-of-responsibility model established by
ADR-0013. A dedicated `HeaderMiddleware` that injects headers in the standard
`handle(request, next_handler)` contract is the correct solution.

A related question arose: does `HeaderMiddleware` overlap with
`AuthMiddleware`? Both mutate `request.headers`, but the concerns are
distinct:

- `AuthMiddleware` manages **credential-bearing headers** (`Authorization`,
  token refresh, TTL caching of tokens).
- `HeaderMiddleware` manages **application-level metadata headers** that have
  no credential lifecycle.

The one grey area is **API key auth** (`X-Api-Key`, `X-Auth-Token`). A
`HeaderMiddleware({"X-Api-Key": "…"})` satisfies simple API key auth without
a dedicated `ApiKeyAuthMiddleware`. This overlap is intentional: it avoids
adding a middleware type for a trivial static header.

## Decision

### Interface

`HeaderMiddleware` and `AsyncHeaderMiddleware` accept a mapping of header
names to values. Values may be static strings or **zero-argument callables**
evaluated once per request (relevant for generated values such as
`X-Correlation-ID`):

```python
from plynt.middleware.header import HeaderMiddleware

transport = HttpxSyncTransport(
    middlewares=[
        HeaderMiddleware(
            {
                "User-Agent": "my-service/1.0",
                "X-Correlation-ID": lambda: str(uuid.uuid4()),
            }
        ),
    ]
)
```

### Non-overwrite semantics

`HeaderMiddleware` **never overwrites a header already present** on the
`Request` object. This allows callers to pin individual headers per request
by setting them explicitly when constructing `Request(headers={…})`.

### Position in the chain

The standard chain order (ADR-0013) is:

```text
HeaderMiddleware → AuthMiddleware → CacheMiddleware → RetryMiddleware → _send_once
```

Placing `HeaderMiddleware` before `AuthMiddleware` ensures:

- Correlation IDs and metadata headers are uniform across all retry attempts.
- `Authorization` (set by `AuthMiddleware`) is never at risk of being
  overwritten.
- If a response cache is present, the cache key is built **after** auth and
  header injection, so auth- and representation-sensitive headers can
  partition cache entries safely.

For use cases that require a **different header value per retry attempt**
(e.g. a per-attempt `X-Request-ID`), place `HeaderMiddleware` after
`RetryMiddleware` in the list.

### Module location

`HeaderMiddleware` and `AsyncHeaderMiddleware` live in
`plynt.middleware.header` and are exported from `plynt.middleware`.

No new dependencies are introduced. This is a Tier 1 core addition per the
middleware extensions plan.

## Consequences

- Callers no longer need to subclass or repeat header injection in service
  methods.
- Simple API key auth can be served by `HeaderMiddleware` without a
  dedicated `ApiKeyAuthMiddleware`.
- The ADR-0013 chain position is extended: `HeaderMiddleware → AuthMiddleware → CacheMiddleware → RetryMiddleware → _send_once`.
- `from_settings()` on `HttpxSyncTransport` / `HttpxAsyncTransport` does
  **not** auto-wire `HeaderMiddleware`. It must be configured explicitly via
  the `middlewares=` constructor argument — consistent with
  `LoggingMiddleware`, which is also opt-in.

## Explicitly out of scope

- **`ApiKeyAuthMiddleware`**: A dedicated middleware type for static API key
  auth headers (`X-Api-Key`, `X-Auth-Token`) is not needed.
  `HeaderMiddleware({"X-Api-Key": "..."})` covers this use case without
  adding a new type.
