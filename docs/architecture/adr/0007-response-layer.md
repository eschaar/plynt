# ADR-0007: Response Layer

## Status

Accepted

## Context

A protocol-agnostic Response abstraction is essential as the counterpart to the
Request layer in Plynth. The core must support multiple HTTP backends (httpx2,
requests, aiohttp) without duplicating their functionality or tightly coupling
higher layers to any specific library.

This raises a key question: how do we define a generic response interface that
allows all layers to work uniformly with responses, without reinventing what
libraries like `httpx2` already provide (`.json()`, `.text()`, `.raise_for_status()`)?

## Decision

### Two-Level Design

The Response Layer uses a two-level design:

1. __`Response` (data carrier)__ — a minimal, library-agnostic dataclass that
   transports produce after converting a raw library response. It holds only
   the essential data: `status_code`, `headers`, and `content` (raw bytes).
   It does __not__ include parsing methods such as `.json()` or `.text()`,
   because these are format-specific, not transport-specific.

1. __`ResponseProtocol` (structural interface)__ — a `typing.Protocol` that
   defines what a response-like object must look like. Any object with the
   right shape (e.g. `httpx2.Response`, `requests.Response`, or
   `plynth.Response`) satisfies this protocol automatically, without needing
   to inherit from it. This is Python structural subtyping.

This design avoids reinventing what HTTP libraries already provide, while
keeping all higher layers (middleware, client, service) decoupled from any
specific library.

### Why `typing.Protocol` and not inheritance?

Inheritance would require all response objects (from httpx2, requests, aiohttp)
to extend a Plynth base class, introducing coupling. With `typing.Protocol`,
any object that has the right attributes and methods is automatically compatible.
This is the standard Python approach for structural interfaces.

### No `ServiceResponse`-style exception marshalling

Prior art in legacy service wrappers used a `ServiceResponse` wrapper to marshal
exceptions across thread boundaries. This was necessary because they used
`threading` to run async work. With modern `asyncio`, exceptions propagate
naturally through `await` chains. This pattern is therefore not needed in
Plynth and would add unnecessary complexity.

### Placement in the Codebase

The Response Layer is split across two files in different namespaces, mirroring
the split in the Transport Layer (see ADR-0006):

- __`plynth.base.response`__ (`base/response.py`) — defines `Response` (the
  protocol-agnostic data carrier) and `ResponseProtocol` (the structural
  interface). Lives in `base/` because it is framework-agnostic and depended
  upon by all layers including `base/transport.py` (Transport abstractions).
- __`plynth.http.response`__ (`http/response.py`) — defines `HttpResponse`,
  which extends `Response` with HTTP request context (`method`, `url`) and
  raises `HttpStatusError` from `raise_for_status()`. Lives in `http/` because
  it introduces HTTP-specific concepts.

There is no `transport/` directory. As documented in ADR-0002, layers are
identified by __file names__, not by directory structure.

### Responsibilities

The Response Layer is responsible for:

- Defining a minimal, library-agnostic `Response` dataclass (status code,
  headers, raw content bytes).
- Defining a `ResponseProtocol` structural interface that any response-like
  object satisfies, enabling decoupled, testable higher layers.
- Ensuring that all transports normalize their library-specific response into
  `plynth.Response` before returning it to higher layers.
- Providing body-decoding convenience on `HttpResponse` (`.encoding`, `.text`,
  `.json()`) — HTTP-layer only; not on the core `Response`.

The Response Layer is __not__ responsible for:

- Parsing content on the core `Response` — raw bytes only; decoding belongs
  in HTTP-specific classes (`HttpResponse`) or the Service Layer.
- Sending or receiving requests (handled by the Transport Layer).
- Business-specific validation or model parsing (handled by the Service Layer).
- Request construction or modification.

### Interfaces

__`Response`__ — protocol-agnostic data carrier, raises `StatusError`:

```python
from dataclasses import dataclass, field
from plynth.base.errors import StatusError

@dataclass
class Response:
    status_code: int
    headers: dict[str, str] = field(default_factory=dict)
    content: bytes = b""

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise StatusError(status_code=self.status_code)
```

__`HttpResponse`__ — HTTP-specific subclass with request context and body
decoding, raises `HttpStatusError`:

```python
@dataclass
class HttpResponse(Response):
    method: str = ""
    url: str = ""

    @property
    def encoding(self) -> str:
        """Charset from Content-Type header, lowercased. Defaults to 'utf-8'."""
        content_type = self.headers.get("content-type", "")
        for part in content_type.split(";"):
            part = part.strip()
            if part.lower().startswith("charset="):
                return part[8:].strip().strip('"').lower()
        return "utf-8"

    @property
    def text(self) -> str:
        """Response body decoded to a string using ``encoding``."""
        return self.content.decode(self.encoding)

    def json(self, **kwargs) -> Any:
        """Decode the response body as JSON."""
        return json.loads(self.text, **kwargs)

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise HttpStatusError(
                status_code=self.status_code,
                method=self.method,
                url=self.url,
            )
```

`raise_for_status()` is included on `Response` so that it satisfies
`ResponseProtocol` out of the box. It is not a parsing helper — it is part
of the structural contract.

`encoding`, `text`, and `json()` are placed on `HttpResponse` (not on the
core `Response`) because body decoding is an HTTP-layer concern. The core
`Response` remains format-agnostic and carries only raw bytes. This matches
how `httpx2.Response` works: `.content` is the raw bytes, `.text` / `.json()`
are HTTP-layer conveniences.

__`ResponseProtocol`__ — structural interface for all higher layers:

```python
from typing import Protocol, runtime_checkable
from collections.abc import Mapping

@runtime_checkable
class ResponseProtocol(Protocol):
    status_code: int
    headers: Mapping[str, str]
    content: bytes

    def raise_for_status(self) -> None: ...
```

Any response object from httpx2, requests, or Plynth itself satisfies this
protocol without inheritance. Adapters can be provided for libraries that use
different attribute names (e.g. aiohttp uses `.status` instead of `.status_code`).

### Error Contract

`raise_for_status()` raises errors from the `plynth.base.errors` hierarchy:

```text
BaseError (core)
└── TransportError
    └── StatusError           — protocol-agnostic (status_code)
        └── HttpStatusError   — HTTP-specific (adds method, url)
        # GrpcStatusError     — future
```

- `Response.raise_for_status()` raises `StatusError` — protocol-agnostic.
- `HttpResponse.raise_for_status()` raises `HttpStatusError`, which carries
  `method` and `url` from the originating request for richer error context.
- Callers catch `HttpStatusError` for HTTP, `StatusError` for general cases,
  or `TransportError` for all transport failures — never a library-specific
  exception like `httpx2.HTTPStatusError`.

The `status_code` (and for HTTP: `method`, `url`) is always available as a
structured attribute on the exception and included in `details` for logging
and serialisation.

## Consequences

- Higher layers (middleware, client, service) depend on `ResponseProtocol`,
  not on any concrete class or HTTP library.
- Transports convert library-specific responses to `plynth.Response`; the
  dataclass is the single source of truth for raw response data in tests.
- Format-specific parsing (JSON, text) is handled by `HttpResponse` for
  HTTP responses and remains absent from the core `Response` primitive.
  The core `Response` stays raw-bytes only.
- Callers working with `HttpResponse` can use `.text` or `.json()` directly
  instead of manually calling `json.loads(response.content)`.
- Mocking is trivial: any object with the right attributes satisfies the
  protocol, no patching of library internals needed.
