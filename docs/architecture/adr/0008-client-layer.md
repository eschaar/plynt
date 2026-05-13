# ADR-0008: Client Layer

## Status

Accepted

## Context

After the Transport Layer (ADR-0006) handles raw request dispatch and the
Response Layer (ADR-0007) normalises the result, a Client Layer is needed that:

- Assembles `Request` objects from a base URL, path, and per-call parameters.
- Manages a set of default headers shared across all calls.
- Exposes a clean, verb-oriented API (`get`, `post`, `put`, `patch`, `delete`).
- Delegates all I/O to an injected transport, keeping itself testable.

Multiple client implementations can exist at this layer level, each targeting
a different protocol or API convention (HTTP, JSON REST, gRPC, etc.). They are
all __Client Layer__ because they share the same architectural role: composing a
transport with request-building logic and returning a `Response`. The distinction
is in what conventions they apply, not in their architectural tier.

## Decision

### One layer, multiple client flavours

The Client Layer is a single architectural tier that contains several concrete
client classes. Currently implemented in `plynth`:

| Class                            | Module           | Description                                 |
| -------------------------------- | ---------------- | ------------------------------------------- |
| `HTTPClient` / `AsyncHTTPClient` | `http/client.py` | Raw HTTP access, no protocol conventions    |
| `APIClient` / `AsyncAPIClient`   | `http/client.py` | JSON REST conventions + typed error raising |

Future additions at the same layer level (examples, not yet implemented):

| Class                            | Module           | Description            |
| -------------------------------- | ---------------- | ---------------------- |
| `GRPCClient` / `AsyncGRPCClient` | `grpc/client.py` | gRPC transport wrapper |

All client classes in this layer live in the namespace that matches their
protocol (e.g., `http/`, `api/`, `grpc/`). The file name `client.py` in each
namespace signals Client Layer membership (see ADR-0002).

### Shared responsibilities across all clients

Every Client Layer implementation is responsible for:

- Constructing or preparing outgoing requests from caller-supplied parameters.
- Merging per-call arguments (headers, params, body) with client-level defaults.
- Delegating dispatch to the injected transport.
- Exposing a conventionally shaped API so callers interact with the client
  the same way regardless of which flavour they use.

Every Client Layer implementation is __not__ responsible for:

- Authentication, retry, or caching.
- Parsing response bodies (`.json()`, `.text()`).
- Business-specific endpoint definitions (handled by the Service Layer).

### HTTPClient — raw HTTP

`HTTPClient` and `AsyncHTTPClient` compose a `SyncTransport` or
`AsyncTransport` with a base URL and default headers. They do __not__ inject
any protocol-specific headers by default and do __not__ raise on 4xx/5xx.

```python
from plynth.base.transport import SyncTransport
from plynth.base.request import Request
from plynth.base.response import Response
from typing import Any

class HTTPClient:
    def __init__(
        self,
        base_url: str,
        transport: SyncTransport,
        headers: dict[str, str] | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._transport = transport
        self._default_headers: dict[str, str] = headers or {}

    def request(
        self,
        method: str,
        path: str,
        *,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        content: bytes | None = None,
    ) -> Response:
        merged = {**self._default_headers, **(headers or {})}
        req = Request(
            method=method,
            url=f"{self._base_url}/{path.lstrip('/')}",
            headers=merged,
            params=params or {},
            content=content,
        )
        return self._transport.send(req)

    def get(self, path: str, *, headers: dict[str, str] | None = None,
            params: dict[str, Any] | None = None) -> Response:
        return self.request("GET", path, headers=headers, params=params)

    # post(), put(), patch(), delete() — same pattern
```

`AsyncHTTPClient` mirrors this design with `async def request()` and
`await self._transport.send(req)`.

### APIClient — JSON REST conventions

`APIClient` extends `HTTPClient` and adds two JSON REST API conventions:

1. Injects `Content-Type: application/json` and `Accept: application/json`
   into every request (merged with any caller-supplied headers).
1. Calls `match_error()` after every response with a 4xx or 5xx status code,
   raising a typed `HttpStatusError` subclass instead of returning silently.

```python
from plynth.http.errors import match_error
from plynth.http.client import HTTPClient
from plynth.base.transport import SyncTransport
from plynth.base.response import Response
from typing import Any

_JSON_HEADERS: dict[str, str] = {
    "Content-Type": "application/json",
    "Accept": "application/json",
}

class APIClient(HTTPClient):
    def __init__(
        self,
        base_url: str,
        transport: SyncTransport,
        headers: dict[str, str] | None = None,
    ) -> None:
        merged = {**_JSON_HEADERS, **(headers or {})}
        super().__init__(base_url, transport, headers=merged)

    def request(self, method: str, path: str, *, headers: dict[str, str] | None = None,
                params: dict[str, Any] | None = None, content: bytes | None = None) -> Response:
        resp = super().request(method, path, headers=headers, params=params, content=content)
        if resp.status_code >= 400:
            raise match_error(
                resp.status_code,
                method=method,
                url=f"{self._base_url}/{path.lstrip('/')}",
            )
        return resp
```

`AsyncAPIClient` mirrors this design using `async def request()`.

#### Typed error hierarchy

`match_error()` (from `plynth.http.errors`) maps a status code to the most
specific `HttpStatusError` subclass, falling back to plain `HttpStatusError`:

```text
HttpStatusError
├── BadRequestError          (400)
├── UnauthorizedError        (401)
├── ForbiddenError           (403)
├── NotFoundError            (404)
├── NotAllowedError          (405)
├── RequestTimeoutError      (408)
├── ConflictError            (409)
├── GoneError                (410)
├── UnprocessableEntityError (422)
├── InternalServerError      (500)
├── OperationFailedError     (500)
├── ServiceUnavailableError  (503)
└── FeatureOfflineError      (503)
```

All errors carry `status_code`, `method`, and `url` as structured attributes.

### Choosing a client

| Need                                   | Use                              |
| -------------------------------------- | -------------------------------- |
| Raw HTTP, any content type             | `HTTPClient` / `AsyncHTTPClient` |
| JSON REST API, typed errors on failure | `APIClient` / `AsyncAPIClient`   |
| gRPC (future)                          | `GRPCClient` / `AsyncGRPCClient` |

### Testing

Because each client injects its transport, all Client Layer implementations
are trivially testable: pass a mock `SyncTransport`/`AsyncTransport` that
returns a pre-built `Response`. No network access is required.

## Consequences

- All protocols and API conventions share the same architectural tier, making
  the layer model easier to reason about.
- Adding a new client flavour (e.g., gRPC) does not introduce a new layer — it
  is a new `client.py` in the appropriate namespace.
- `APIClient` can extend `HTTPClient` through standard inheritance without
  duplicating request-building logic.
- Swapping the transport requires changing only the constructor argument.
