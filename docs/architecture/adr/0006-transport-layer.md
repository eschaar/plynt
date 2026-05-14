# ADR-0006: Transport Layer

## Status

Accepted

## Context

Plynth must support both synchronous and asynchronous HTTP communication
without duplicating business logic. The transport layer is the lowest-level
abstraction responsible for sending HTTP requests and returning raw responses.

It must be:

- Swappable: users can bring their own HTTP library.
- Execution-model agnostic: sync and async transports share the same interface.
- Testable: fully mockable without real network calls.
- Minimal: no middleware, auth, retry, or caching logic lives here.

## Decision

### Placement in the Codebase

The Transport Layer is split across two files that live in different namespaces:

- __`plynth.base.transport`__ (`base/transport.py`) — defines the abstract
  contracts `SyncTransport` and `AsyncTransport`. Lives in `base/` because it is a
  framework-agnostic primitive that higher layers depend on, and because
  placing it there avoids a circular import with `base/request.py`.
- __`plynth.http.transport`__ (`http/transport.py`) — provides the concrete
  httpx-backed implementations `HttpxSyncTransport` and `HttpxAsyncTransport`.
  Lives in `http/` because it introduces an `httpx` dependency and is
  HTTP-specific.

There is no dedicated `transport/` directory. As documented in ADR-0002, layers
are identified by __file names__, not by directory structure.

### Responsibilities

The transport layer is responsible __only__ for:

- Sending a prepared `Request` object over the network.
- Returning a raw `Response` object.
- Enforcing timeouts and SSL behavior.

The __concrete base transport__ (e.g. `HttpxSyncTransport`) is __not__
responsible for:

- Authentication or token management.
- Retry logic.
- Caching.
- Request building or header injection.
- Response parsing or error mapping.

These cross-cutting concerns are handled by `BaseSyncTransport` /
`BaseAsyncTransport` — abstract bases in `plynth.base.transport` that introduce
a fixed `send()` implementation orchestrating cache → auth → retry →
`_send_once()` → reactive re-auth (401) → cache store. Concrete transports
extend these bases and implement only `_send_once()` with the actual network
I/O. See ADR-0013 for the full design.

### Abstract Interface

Plynth defines its own `Request` and `Response` types in `plynth.base.request`
and `plynth.base.response` respectively. These are library-agnostic data carriers
that do not depend on `requests`, `httpx`, or any other HTTP library.

Two separate abstract base classes define the sync and async contracts
(`plynth.base.transport`):

```python
from abc import ABC, abstractmethod
from plynth.base.request import Request
from plynth.base.response import Response

class SyncTransport(ABC):
    """Contract for synchronous transports."""

    @abstractmethod
    def send(self, request: Request) -> Response:
        """Send a request and return a raw response."""
        ...

class AsyncTransport(ABC):
    """Contract for asynchronous transports."""

    @abstractmethod
    async def send(self, request: Request) -> Response:
        """Send a request and return a raw response asynchronously."""
        ...
```

### Concrete Implementation

`HttpxSyncTransport` and `HttpxAsyncTransport` in `plynth.http.transport`
implement these contracts using `httpx`. Both return `HttpResponse` (from
`plynth.http.response`), which satisfies `ResponseProtocol` and carries the
originating request's method and URL for richer error messages.

Concrete transports do not implement cross-cutting concerns (auth, retry,
caching) themselves. These are handled by `BaseSyncTransport` /
`BaseAsyncTransport` — abstract base classes in `plynth.base.transport` that
sit between `SyncTransport`/`AsyncTransport` and the concrete implementations.
See ADR-0013 for the full transport base class design.

`httpx` is an optional dependency and must be installed via:

```bash
pip install plynth[httpx]
```

## Consequences

- The transport layer is fully decoupled from business logic and higher-level
  concerns.
- Users can swap in their own HTTP libraries or mocks for testing.
- Sync and async execution are both supported without code duplication.
- The abstract contracts in `base/transport.py` remain dependency-free and usable
  without installing `httpx`.
- Cross-cutting concerns (auth, retry, cache) are handled once in
  `BaseSyncTransport` / `BaseAsyncTransport` (`plynth.base.transport`) and
  inherited by all concrete transports — see ADR-0013.
