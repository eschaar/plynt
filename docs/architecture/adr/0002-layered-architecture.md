# ADR-0002: Layered Architecture

## Status

Accepted

## Context

To ensure maintainability, extensibility, and clarity, the library is structured
into distinct conceptual layers. Each layer has a single responsibility and
clear boundaries.

## Decision

### Layers are defined by file names, not directories

The layered architecture is defined by **file names**, not by the directory that
contains a file. Directories (`base/`, `middleware/`, `http/`) are namespace
groupings that help organise related primitives — they are not architectural
tier boundaries.

A file's layer membership is evident from its **name** (e.g., `transport.py`,
`client.py`, `response.py`) and its docstring, not from its directory.

### Directory structure

```text
src/plynth/
  base/              ← protocol-agnostic primitives; no framework dependencies
    cache.py         — CacheBackend protocol + SupportsTTL/Stats/SizeInfo
                       + CacheConfigBase marker
    errors.py        — error base classes
    mapping.py       — ErrorMapper ABC
    middleware.py    — SyncMiddleware / AsyncMiddleware protocols
    policies.py      — RetryPolicy dataclass (+ future TimeoutPolicy, ...)
    request.py       — Request dataclass
    response.py      — Response dataclass + ResponseProtocol
    settings.py      — Settings base (pydantic-settings)
    transport.py     — SyncTransport / AsyncTransport ABCs
                       + BaseSyncTransport / BaseAsyncTransport

  middleware/        ← protocol-agnostic middleware implementations
    cache.py         — CacheMiddleware / AsyncCacheMiddleware
    logging.py       — LoggingMiddleware + request/response log filters
    retry.py         — RetryMiddleware / AsyncRetryMiddleware

  cache/             ← protocol-agnostic cache backends; optional [cache] extra
    __init__.py      — CacheConfig type alias + cache_from_config() factory
                       + public re-exports of all backends and config types
    dummy.py         — DummyCache + DummyCacheConfig
    locmem.py        — LocMemCache + LocMemCacheConfig
    redis.py         — RedisCache + RedisCacheConfig (requires redis)
    cachetools.py    — CachetoolsCache (requires cachetools)

  http/              ← HTTP-specific layer; requires httpx2
    policies.py      — HttpRetryPolicy (retryable status codes)
    middleware/      ← HTTP-specific middleware implementations
      auth.py        — BearerTokenAuthMiddleware, BasicAuthMiddleware,
                       OAuth2AuthMiddleware (requires httpx2 for token fetch)
    client.py        — HTTPClient / AsyncHTTPClient
                       + APIClient / AsyncAPIClient (JSON REST conventions)
    errors.py        — HttpStatusError + typed REST error hierarchy
                       + match_error()
    mapping.py       — APIErrorMapper
    renderer.py      — Renderer protocol + JSONRenderer
    response.py      — HttpResponse
    service.py       — HTTPService / AsyncHTTPService
                       + APIService / AsyncAPIService
    settings.py      — HTTPSettings + ApiSettings
    transport.py     — HttpxSyncTransport / HttpxAsyncTransport

  connectors/        ← business-specific SaaS connector packages
    salesforce/

  adapters/          ← framework bridging (Django, FastAPI, Flask — planned)
```

Future protocol namespaces follow the same pattern as `http/`:

```text
  grpc/              ← (future) gRPC layer
    middleware/
      auth.py        — gRPC credential middleware
      retry.py       — gRPC-specific retry policy
    transport.py     — gRPC-backed transport implementation
    client.py        — gRPC channel wrapper
    service.py       — base service for gRPC consumers/producers
    settings.py      — GRPCSettings (host, port, credentials, ...)
```

Each protocol namespace (`http/`, `grpc/`, ...) is self-contained. Protocol
namespaces import from `base/` and `middleware/`, but never from each other.
This keeps imports ergonomic (`from plynth.http.transport import HttpxSyncTransport`)
and makes each namespace independently installable via
extras.

### Namespace responsibilities

**`base/`** contains only protocol-agnostic abstractions: protocols, ABCs,
dataclasses, and base classes that carry no framework dependency. Nothing in
`base/` may import from `middleware/`, `http/`, `cache/`, or any protocol
namespace.

**`middleware/`** contains protocol-agnostic middleware *implementations* that
work with any transport backed by `BaseSyncTransport` / `BaseAsyncTransport`.
Files here import from `base/` only.

**`cache/`** contains protocol-agnostic concrete cache backend implementations
that satisfy the `CacheBackend` protocol defined in `base/cache.py`. Backends
here do not touch `httpx2` and may be reused by any protocol namespace
(`http/`, `grpc/`, ...). Optional third-party dependencies (`redis`,
`cachetools`) are isolated per file so that installing only the stdlib-backed
backends does not require those packages. Files here import from `base/` only.

**`http/`** contains everything that touches `httpx2`: the transport
implementation, concrete auth middleware, HTTP-specific retry policy,
response type, error hierarchy, and the client/service/settings types. The
`http/middleware/` subdirectory groups the HTTP-specific middleware
implementations separately from the transport and client code. HTTP settings
reference cache config types from `cache/` via `plynth.cache`.

**`connectors/`** contains business-specific SaaS connector packages (e.g. `salesforce/`).
These import from `base/`, `middleware/`, and a single protocol namespace
(`http/`). They never import from another connector.

**`adapters/`** contains framework bridging modules (Django, FastAPI, Flask —
planned). Adapters depend on the core through public interfaces only; no
framework assumptions leak back into the core.

### Sync and async co-location

Sync and async variants of the same concept always live in the same file
(e.g. `BaseSyncTransport` and `BaseAsyncTransport` in `base/transport.py`,
`RetryMiddleware` and `AsyncRetryMiddleware` in `middleware/retry.py`).
Splitting them across files would invite logic drift and provide no benefit,
since both variants are always shipped together.

### Layer ordering

Layers are ordered by dependency and logical build-up:

```mermaid
flowchart LR
    Req[Request] --> Transport --> Response --> Client --> Service
```

1. **Request Layer** (`base/request.py`)

   - Defines the protocol-agnostic `Request` dataclass
     (method, url, headers, params, content).
   - All outgoing requests start here; it is the fundamental data carrier
     for all higher layers.

1. **Transport Layer** (`base/transport.py` + `http/transport.py`)

   - `base/transport.py` defines two tiers of transport abstractions:
     - `SyncTransport` / `AsyncTransport` — minimal ABCs defining only
       `send()`. Use for test doubles or non-HTTP protocols.
     - `BaseSyncTransport` / `BaseAsyncTransport` — concrete `send()` that
       drives the middleware chain, terminating at `_send_once()`. Subclass
       these and implement only `_send_once()`.
   - `http/transport.py` provides `HttpxSyncTransport` and
     `HttpxAsyncTransport`, which extend the base transports and implement
     `_send_once()` using `httpx2`.
   - Transports are swappable without affecting any higher layer.

1. **Response Layer** (`base/response.py` + `http/response.py`)

   - `base/response.py` defines `Response` (minimal data carrier: status
     code, headers, raw bytes) and `ResponseProtocol` (structural interface).
   - `http/response.py` defines `HttpResponse`, which extends `Response`
     with the originating request's `method` and `url`, and raises
     `HttpStatusError` from `raise_for_status()`.
   - Higher layers depend on `ResponseProtocol`, never on a concrete class
     or any specific HTTP library.

1. **Client Layer** (`http/client.py`)

   - A single file contains two client flavours at the same architectural
     tier, distinguished only by the conventions they apply:
     - `HTTPClient` / `AsyncHTTPClient` — raw HTTP access; does not raise
       on 4xx/5xx.
     - `APIClient` / `AsyncAPIClient` — extends `HTTPClient` with JSON REST
       conventions: injects `Content-Type: application/json` and
       `Accept: application/json`, and raises a typed error via
       `match_error()` for 4xx/5xx responses.
   - See ADR-0008 for the full Client Layer decision.

1. **Service Layer** (`http/service.py` + domain packages)

   - `http/service.py` contains base classes for both HTTP and API
     conventions: `HTTPService` / `AsyncHTTPService` and `APIService` /
     `AsyncAPIService`. These accept the matching client via constructor
     injection and provide `self._client`.
   - Business-specific services extend these base classes, adding endpoint
     methods and returning domain model objects (never raw `Response`).
   - Request body serialisation is handled by an optional `Renderer`
     (defined in `http/renderer.py`) injected into the service.
   - See ADR-0009 for the full Service Layer decision.

## Consequences

- Each layer can be developed, tested, and extended independently.
- The architecture supports both synchronous and asynchronous execution
  without duplicating business logic.
- Protocol namespaces (`http/`, `grpc/`, ...) are independently installable
  via extras and never depend on each other.
- The `base/` and `middleware/` namespaces are always available as a
  dependency-free foundation.
