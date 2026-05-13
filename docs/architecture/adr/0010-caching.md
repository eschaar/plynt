# ADR-0010: Caching

## Status

Accepted

## Implementation Notes

**Implemented:** The `CacheBackend` Protocol (`plynth.base.cache`).

**Superseded:** The `cache=` constructor parameter on `BaseSyncTransport` /
`BaseAsyncTransport` (original proposal, ADR-0013) has been replaced by
`CacheMiddleware` / `AsyncCacheMiddleware` in `plynth.middleware.cache`.
Consumers pass the middleware in the `middlewares` list:

```python
from plynth.middleware.cache import CacheMiddleware

transport = HttpxSyncTransport(middlewares=[CacheMiddleware(my_cache)])
```

**Implemented:** Concrete built-in backends in `plynth.cache`. `DummyCache`,
`LocMemCache`, `CachetoolsCache` (requires `[cache]` extra), and `RedisCache`
(requires `[cache]` extra) are available.

**Implemented:** Typed cache configuration (`DummyCacheConfig`,
`LocMemCacheConfig`, `RedisCacheConfig`, `CacheConfig`, `cache_from_config()`)
in `plynth.cache`. The typed config pattern replaces the earlier URI-string
approach.

## Context

Some consumers of Plynth need to cache HTTP responses to avoid redundant
network calls — for example when polling a slow or rate-limited API. Caching
behaviour is not universally desired, so it must not be part of the core
package (ADR-0003).

Framework integrations (Django, FastAPI) may already have their own caching
backends. A solution must therefore remain framework-agnostic at the core
level and allow framework-specific adapters to plug in their own backends.

The earlier approach exposed `cache_backend: str` and `auth_cache_backend: str`
fields on `HTTPSettings` whose values were location URIs
(e.g. `"redis://localhost:6379/0"`). This caused several problems:

1. **No structured options.** Key prefix, socket timeout, TLS certificates,
   and retry-on-timeout cannot be expressed in a single URI string.
1. **Type mixing.** A single string conflated the backend type (from the URI
   scheme) with the location and all options.
1. **Env-driven coupling.** URI strings are pydantic env-var fields, making
   it awkward to configure non-secret options (key prefix, timeouts) via code
   while secrets come from environment variables.
1. **No construction-time validation.** An invalid URI was only detected when
   `from_settings()` was first called.

## Decision

### Installation Extra

Caching support is shipped as an optional install extra:

```text
pip install plynth[cache]
```

### Abstract Cache Interface

A `CacheBackend` protocol is defined in `plynth.base.cache`. It describes the
minimal key/value interface that any backend must implement:

```python
class CacheBackend(Protocol):
    def get(self, key: str) -> Response | None: ...
    def set(self, key: str, value: Response, ttl: int | None = None) -> None: ...
```

TTL and eviction are implementation details managed by the concrete backend.
Framework-specific adapters (Django cache, Redis, in-memory) implement this
Protocol without inheriting from any base class.

### Caching Via CacheMiddleware

With the chain-of-responsibility middleware contract (ADR-0013), caching is
implemented as `CacheMiddleware` / `AsyncCacheMiddleware` in
`plynth.middleware.cache`. Only `GET` requests are cached by default.

```python
from plynth.middleware.cache import CacheMiddleware
from plynth.http.transport import HttpxSyncTransport

transport = HttpxSyncTransport(
    middlewares=[CacheMiddleware(my_cache)],
)
```

`CacheMiddleware.handle()` short-circuits on a GET cache hit and stores
successful GET responses on the way out.

### Cache Key Strategy

The cache key is derived deterministically from:

- HTTP method
- Fully qualified URL (including query parameters)

Request body and non-idempotent headers are excluded.

### Typed Configuration Pattern

Introduce typed configuration dataclasses for each cache backend:

- `DummyCacheConfig` — no-op backend for testing, no options.
- `LocMemCacheConfig(max_size)` — in-process, thread-safe cache.
- `RedisCacheConfig(location, key_prefix, socket_timeout, ...)` — Redis-backed
  cache with full connection options.

The union type alias
`CacheConfig = LocMemCacheConfig | DummyCacheConfig | RedisCacheConfig`
replaces the URI string concept.

A factory function `cache_from_config(config: CacheConfig) -> CacheBackend`
constructs the appropriate backend instance from a config object.

### Settings API

`HTTPSettings` exposes three `@property` methods:

```python
@property
def caches(self) -> dict[str, CacheConfig] | None:
    return None  # override in subclass to enable caching

@property
def default_cache(self) -> str | None:
    return None  # key in caches to use for response caching

@property
def default_auth_cache(self) -> str | None:
    return None  # key in caches to use for OAuth2 token caching
```

The old string fields `cache_backend` and `auth_cache_backend` are removed.

### Subclass Usage

```python
from plynth.cache import RedisCacheConfig

class SalesforceSettings(HTTPSettings):
    redis_url: str = ""  # SF_REDIS_URL=redis://...

    @property
    def caches(self) -> dict[str, CacheConfig] | None:
        if not self.redis_url:
            return None
        return {
            "responses": RedisCacheConfig(
                location=self.redis_url,
                key_prefix="sf:http:",
            ),
            "tokens": RedisCacheConfig(
                location=self.redis_url,
                key_prefix="sf:tokens:",
                socket_timeout=2.0,
            ),
        }

    @property
    def default_cache(self) -> str | None:
        return "responses"

    @property
    def default_auth_cache(self) -> str | None:
        return "tokens"
```

The URL/location (a secret, from env or Vault) is separated from backend
options (non-secret, defined in code). `RedisCacheConfig.__post_init__`
validates the URL scheme at object construction time — fail-fast.

### `from_settings()` Logic

```python
caches = settings.caches
response_cache = (
    cache_from_config(caches[settings.default_cache])
    if caches and settings.default_cache and settings.default_cache in caches
    else None
)
auth_cache = (
    cache_from_config(caches[settings.default_auth_cache])
    if caches and settings.default_auth_cache
        and settings.default_auth_cache in caches
    else None
)
```

### Explicit Opt-In Only

Caching is never enabled implicitly. Consumers either pass `CacheMiddleware`
directly or configure the `caches` property — both require explicit code.

### Scope Boundaries

| Concern                                          | Location                       |
| ------------------------------------------------ | ------------------------------ |
| `CacheBackend` Protocol                          | `plynth.base.cache`            |
| `CacheMiddleware` / `AsyncCacheMiddleware`       | `plynth.middleware.cache`      |
| `CacheConfig` type alias + `cache_from_config()` | `plynth.cache`                 |
| `DummyCache` + `DummyCacheConfig`                | `plynth.cache.dummy`           |
| `LocMemCache` + `LocMemCacheConfig`              | `plynth.cache.locmem`          |
| `RedisCache` + `RedisCacheConfig`                | `plynth.cache.redis`           |
| `CachetoolsCache`                                | `plynth.cache.cachetools`      |
| Django cache adapter                             | `plynth.django.cache` (future) |

The public import path is `plynth.cache`:

```python
from plynth.cache import RedisCacheConfig, cache_from_config
```

## Consequences

- Consumers that do not install `[cache]` are unaffected.
- The `CacheBackend` Protocol ensures any backend can be swapped without
  changing application code.
- Structured config objects expose all backend options as typed, named fields
  with IDE auto-complete and static type checking.
- The URL/location (a secret) is separated from backend options (non-secret).
- Properties are excluded from pydantic field parsing, which keeps the
  env-var surface area clean.
- Subclasses can define and name multiple distinct caches (e.g. `"responses"`,
  `"tokens"`) and select them independently.
- Cache middleware is testable in isolation using a mock `CacheBackend`.
- Token/auth caching (OAuth2 token reuse) uses the same `CacheBackend`
  protocol but is managed internally by OAuth2 auth middleware — not by this
  caching layer.

## Related

- ADR-0003 — Dependency Policy (optional extras model)
- ADR-0004 — Settings and Configuration (caches / default_cache properties)
- ADR-0006 — Transport Layer (interception point for caching)
- ADR-0008 — Client Layer (consumers of transports)
- ADR-0013 — Transport Base Class (canonical middleware ordering)
