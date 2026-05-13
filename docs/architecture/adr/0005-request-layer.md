# ADR-0005: Request Layer

## Status

Accepted

## Context

A protocol-agnostic Request abstraction is essential as the foundation for all
layers in Plynth. This layer provides a uniform representation of outgoing
requests, independent of the transport, protocol, or domain used. This makes
middleware, clients, transports, and services generic, testable, and extensible.

## Decision

### Placement in the Codebase

The `Request` class is implemented as a standalone module (`request.py`) within
the `base/` namespace: `plynth.base.request`.

It lives in `base/` rather than `http/` for a deliberate structural reason: the
Transport ABCs (`SyncTransport`, `AsyncTransport`) in `core/base.py` reference
`Request` as their parameter type. If `Request` were placed in `http/`, a
circular import would result (`core/base.py` → `http/` → `http/transport.py` →
`core/base.py`). Moving `Request` to `base/` breaks this cycle while keeping
the type available across all layers.

This placement reinforces the reality that `Request` is a protocol-agnostic data
carrier — its fields (method, url, headers, params, content) are not HTTP-only
concepts, even though the current implementation targets HTTP.

Only if, in the future, multiple request types, utilities, or submodules are
needed should a dedicated subdirectory be considered.

### Responsibilities

The Request Layer is responsible for:

- Defining a universal, library-agnostic `Request` dataclass
  (method, url, headers, params, content).
- Ensuring that all layers (middleware, client, transport, service) use this
  abstraction for outgoing requests.
- Enabling generic middleware, logging, authentication, retry, etc., without
  dependency on a specific HTTP library.

The Request Layer is __not__ responsible for:

- Actually sending requests (handled by the Transport Layer).
- Business-specific validation or endpoint definitions (handled by the Service Layer).
- Response parsing or error mapping.

### Abstract Interface

`Request` is defined in `plynth.base.request` as a plain dataclass:

```python
from dataclasses import dataclass, field
from typing import Any

@dataclass
class Request:
    method: str
    url: str
    headers: dict[str, str] = field(default_factory=dict)
    params: dict[str, Any] = field(default_factory=dict)
    content: bytes | None = None
```

All transports, middleware, and clients work with this type.

## Amendment — per-request timeout (ADR-0005-A1)

Decision: Add an optional `timeout` field to `Request`:

```python
@dataclass
class Request:
    method: str
    url: str
    headers: dict[str, str] = field(default_factory=dict)
    params: dict[str, Any] = field(default_factory=dict)
    content: bytes | None = None
    timeout: float | None = None
```

When `timeout` is set, the httpx transport passes it as the `timeout=`
argument to `client.request()`, overriding the transport-level timeout
configured via `HTTPSettings`. When `None` (the default), the transport's
configured timeout applies unchanged.

Rationale: Per-request timeout override is a common need (e.g. bulk
export calls that legitimately take longer). A `TimeoutMiddleware` was
considered but rejected: it would either affect all requests equally
(same as transport-level settings already do) or require
framework-specific extension points. A plain field on `Request` is
simpler, testable, and keeps the override close to the call site.

## Consequences

- All layers are decoupled from specific HTTP libraries.
- Middleware, clients, and services are simpler to test and extend.
- The architecture is ready for additional protocols (HTTP, gRPC, etc.) in the
  future if needed.
