# ADR-0013: Transport Base Class

## Status

Accepted

## Context

ADRs 0010 (Caching), 0011 (Authentication), and 0012 (Retry) proposed
implementing cross-cutting concerns as transport wrappers using the object
Decorator pattern. While architecturally correct in isolation, this had
practical drawbacks:

- **User-facing complexity**: consumers must nest wrappers explicitly.
- **No code reuse across transports**: each new transport re-applies the same
  wrappers.
- **Composition order is the caller's responsibility.**

The first middleware protocol used a `before_send` / `after_send` split:

```python
class SyncMiddleware(Protocol):
    def before_send(self, request: Request) -> None: ...
    def after_send(self, request: Request, response: Response) -> None: ...
```

This works for observation (logging, timing) but has a fundamental limitation:
neither hook can return a `Response`. This prevents:

- **Response caching** — returning a cached response before touching the
  network requires short-circuiting the pipeline, which `-> None` cannot do.
- **Circuit breakers** and **response transformation**.

The standard industry solution — used by Django, ASGI, Express.js, and ASP.NET
Core — is a **chain-of-responsibility** ("onion") pattern where each middleware
wraps the next via a `next_handler` callable.

This ADR supersedes both the transport-wrapper approach from ADRs 0010, 0011,
and 0012, and the `before_send` / `after_send` middleware contract.

## Decision

### Two-Tier Transport Hierarchy

**Tier 1 — Abstract contracts** (`plynth.base.transport`):

```python
class SyncTransport(ABC):
    @abstractmethod
    def send(self, request: Request) -> Response: ...

class AsyncTransport(ABC):
    @abstractmethod
    async def send(self, request: Request) -> Response: ...
```

**Tier 2 — Abstract base with middleware chain** (`plynth.base.transport`):

```python
class BaseSyncTransport(SyncTransport):
    def __init__(
        self,
        *,
        middlewares: list[SyncMiddleware] | None = None,
    ) -> None:
        self._middlewares = list(middlewares) if middlewares else []

    def send(self, request: Request) -> Response:
        chain = self._build_middleware_chain(self._send_once)
        return chain(request)

    def _build_middleware_chain(self, innermost):
        handler = innermost
        for mw in reversed(self._middlewares):
            handler = lambda req, _mw=mw, _next=handler: _mw.handle(req, _next)
        return handler

    @abstractmethod
    def _send_once(self, request: Request) -> Response: ...
```

`BaseAsyncTransport` mirrors this design with `async def send()` and
`async def _send_once()`.

### Middleware Protocol: `handle(request, next_handler)`

`SyncMiddleware` and `AsyncMiddleware` in `plynth.base.middleware` use a single
`handle(request, next_handler)` method:

```python
from collections.abc import Awaitable, Callable

NextSyncHandler = Callable[[Request], Response]
NextAsyncHandler = Callable[[Request], Awaitable[Response]]

class SyncMiddleware(Protocol):
    def handle(
        self, request: Request, next_handler: NextSyncHandler
    ) -> Response: ...

class AsyncMiddleware(Protocol):
    async def handle(
        self, request: Request, next_handler: NextAsyncHandler
    ) -> Response: ...
```

Each middleware receives:

- `request` — the outgoing request; may be inspected or mutated.
- `next_handler` — the rest of the chain; call it to continue, skip it to
  short-circuit.

This replaces the `before_send` / `after_send` split. The chain-of-responsibility
model enables caching (short-circuit on GET hit), circuit breakers, and
response transformation.

### Chain Composition and Execution Order

`_build_middleware_chain` wraps `_send_once` with each middleware in reverse
list order so that `middlewares[0]` is outermost (called first):

Execution order for `middlewares = [A, B, C]`:

```text
A.handle (enter)
  B.handle (enter)
    C.handle (enter)
      _send_once   ← pure network I/O
    C.handle (exit)
  B.handle (exit)
A.handle (exit)
```

### Canonical Middleware Ordering

```python
middlewares = [
    CacheMiddleware(...),           # outermost
    OAuth2AuthMiddleware(...),      # or BearerToken / Basic
    RetryMiddleware(policy),        # innermost above I/O
]
```

Rationale:

- **Cache first**: avoids all network I/O on a cache hit, and skips auth.
- **Auth before retry**: every retry attempt carries the current credentials.
- **Retry innermost**: retries wrap only the network call, not auth or cache.

### Concrete Transport Implements Only I/O

```python
class HttpxSyncTransport(BaseSyncTransport):
    def __init__(
        self,
        *,
        client: httpx2.Client | None = None,
        middlewares: list[SyncMiddleware] | None = None,
        log_bodies: bool = False,
    ) -> None:
        super().__init__(middlewares=middlewares)
        self._client = client or httpx2.Client()

    def _send_once(self, request: Request) -> Response:
        # Pure httpx2 I/O — no auth, retry, or cache logic here.
        ...
```

### Settings Integration

`HttpxSyncTransport.from_settings(settings: HTTPSettings)` constructs a fully
configured transport from the `auth`, `caches`, and `max_attempts` settings:

```python
@classmethod
def from_settings(cls, settings: HTTPSettings) -> HttpxSyncTransport:
    middlewares = [
        *([CacheMiddleware(cache_from_config(...))] if response_cache else []),
        *([auth_from_config(settings.auth, ...)] if settings.auth else []),
        RetryMiddleware(HttpRetryPolicy(max_attempts=settings.max_attempts)),
    ]
    return cls(client=_build_httpx_client(settings), middlewares=middlewares)
```

Users who need a custom configuration construct the transport directly:

```python
from plynth.middleware.retry import RetryMiddleware
from plynth.http.middleware.auth import BearerTokenAuthMiddleware
from plynth.cache import LocMemCache
from plynth.middleware.cache import CacheMiddleware
from plynth.http.policies import HttpRetryPolicy

transport = HttpxSyncTransport(
    client=httpx2.Client(...),
    middlewares=[
        CacheMiddleware(LocMemCache()),
        BearerTokenAuthMiddleware(settings.bearer_token),
        RetryMiddleware(HttpRetryPolicy(max_attempts=3)),
    ],
)
```

### Advice for Custom Transports

| Use case                                | Recommendation                                               |
| --------------------------------------- | ------------------------------------------------------------ |
| HTTP-based transport (httpx2, aiohttp)  | Extend `BaseSyncTransport` / `BaseAsyncTransport`            |
| Protocol with its own auth model (gRPC) | Extend `SyncTransport` / `AsyncTransport` directly           |
| Test double / mock                      | Extend `SyncTransport` — single `send()` method to implement |

### Scope Boundaries

| Concern                                        | Location                             |
| ---------------------------------------------- | ------------------------------------ |
| `SyncTransport` / `AsyncTransport` ABCs        | `plynth.base.transport`              |
| `SyncMiddleware` / `AsyncMiddleware` protocols | `plynth.base.middleware`             |
| `BaseSyncTransport` / `BaseAsyncTransport`     | `plynth.base.transport`              |
| `HttpxSyncTransport` / `HttpxAsyncTransport`   | `plynth.http.transport`              |
| Settings-to-transport wiring                   | `HttpxSyncTransport.from_settings()` |

## Consequences

- Users configure cross-cutting concerns as constructor arguments — no wrapper
  nesting visible in application code.
- Middleware can short-circuit the pipeline — caching, circuit breakers, and
  auth pre-checks are all possible without changing core transport code.
- `_send_once()` in concrete transports contains only I/O logic.
- A new transport implementation (e.g. `AiohttpAsyncTransport`) inherits auth,
  retry, and cache behaviour for free by extending `BaseAsyncTransport`.
- Composition order is canonical and enforced in one place.
- **Breaking change** to the middleware protocol: `before_send` / `after_send`
  are replaced by `handle`. Any existing user-defined middleware must be
  updated.
- The `cache=` constructor parameter is removed from `BaseSyncTransport` and
  `BaseAsyncTransport`. Consumers must pass `CacheMiddleware(cache)` in the
  middlewares list instead.

## Related

- ADR-0003 — Dependency Policy
- ADR-0004 — Settings and Configuration
- ADR-0006 — Transport Layer
- ADR-0008 — Client Layer
- ADR-0010 — Caching (CacheMiddleware)
- ADR-0011 — Authentication (auth middleware)
- ADR-0012 — Retry Strategy (RetryMiddleware)
