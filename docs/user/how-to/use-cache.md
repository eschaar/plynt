# How to use caching

Use `CacheMiddleware` to cache `GET` responses at the transport level.

## Choose a backend

| Backend           | When to use                                                   |
| ----------------- | ------------------------------------------------------------- |
| `LocMemCache`     | Single process, fast, no dependencies                         |
| `CachetoolsCache` | Single process with LRU/TTL eviction and a size limit         |
| `RedisCache`      | Multiple processes or workers; shared cache                   |
| `DummyCache`      | Tests — always misses; disables caching without changing code |

## In-process cache

```python
from plynth.cache import LocMemCache
from plynth.middleware.cache import CacheMiddleware
from plynth.http.transport import HttpxSyncTransport

transport = HttpxSyncTransport(
    middlewares=[CacheMiddleware(LocMemCache(), ttl=300)]
)
```

## Redis shared cache

```python
import redis
from plynth.cache import RedisCache
from plynth.middleware.cache import CacheMiddleware
from plynth.http.transport import HttpxSyncTransport

cache = RedisCache(
    redis.Redis(host="localhost", port=6379, db=0),
    prefix="my-service:",
)
transport = HttpxSyncTransport(
    middlewares=[CacheMiddleware(cache)]
)
```

## LRU cache with a size limit

```python
from cachetools import LRUCache
from plynth.cache import CachetoolsCache
from plynth.middleware.cache import CacheMiddleware

cache = CachetoolsCache(LRUCache(maxsize=512))
transport = HttpxSyncTransport(
    middlewares=[CacheMiddleware(cache)]
)
```

## Disable caching in tests

```python
from plynth.cache import DummyCache
from plynth.middleware.cache import CacheMiddleware

transport = HttpxSyncTransport(
    middlewares=[CacheMiddleware(DummyCache())]
)
```

Alternatively, omit `CacheMiddleware` entirely in the test transport.

## Placement in the middleware stack

Place `CacheMiddleware` **outermost** (first in the list). A cache hit
skips auth token fetching, retry, circuit breaking, and network I/O:

```python
middlewares = [
    CacheMiddleware(cache, ttl=60),  # outermost
    auth_middleware,
    RetryMiddleware(...),
    CircuitBreakerMiddleware(...),
]
```

## Async

Use `AsyncCacheMiddleware` with `HttpxAsyncTransport`. The cache backend is
the same; no async-specific backend is needed:

```python
from plynth.middleware.cache import AsyncCacheMiddleware

transport = HttpxAsyncTransport(
    middlewares=[AsyncCacheMiddleware(LocMemCache(), ttl=300)]
)
```

## Reference

- All cache backends with full configuration options:
  [Cache backends reference](../reference/cache-backends.md).
