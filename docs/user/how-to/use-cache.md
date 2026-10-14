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
from plynt.cache import LocMemCache
from plynt.middleware.cache import CacheMiddleware
from plynt.http.transport import HttpxSyncTransport

transport = HttpxSyncTransport(middlewares=[CacheMiddleware(LocMemCache(), ttl=300)])
```

## Redis shared cache

```python
import redis
from plynt.cache import RedisCache
from plynt.middleware.cache import CacheMiddleware
from plynt.http.transport import HttpxSyncTransport

cache = RedisCache(
    redis.Redis(host="localhost", port=6379, db=0),
    prefix="my-service:",
)
transport = HttpxSyncTransport(middlewares=[CacheMiddleware(cache)])
```

## Redis shared cache with TLS or custom SSL settings

Use `redis.Redis(...)` SSL options directly and pass the configured client to
`RedisCache`.

```python
import redis
from plynt.cache import RedisCache
from plynt.middleware.cache import CacheMiddleware
from plynt.http.transport import HttpxSyncTransport

redis_client = redis.Redis(
    host="redis.internal",
    port=6380,
    db=0,
    ssl=True,
    ssl_ca_certs="/etc/ssl/certs/ca.pem",
    ssl_cert_reqs="required",
)

cache = RedisCache(redis_client, prefix="my-service:")
transport = HttpxSyncTransport(middlewares=[CacheMiddleware(cache, ttl=300)])
```

If your platform requires different TLS options, configure them on the Redis
client the same way and keep `RedisCache` unchanged.

## LRU cache with a size limit

```python
from cachetools import LRUCache
from plynt.cache import CachetoolsCache
from plynt.middleware.cache import CacheMiddleware

cache = CachetoolsCache(LRUCache(maxsize=512))
transport = HttpxSyncTransport(middlewares=[CacheMiddleware(cache)])
```

## Disable caching in tests

```python
from plynt.cache import DummyCache
from plynt.middleware.cache import CacheMiddleware

transport = HttpxSyncTransport(middlewares=[CacheMiddleware(DummyCache())])
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
from plynt.middleware.cache import AsyncCacheMiddleware

transport = HttpxAsyncTransport(
    middlewares=[AsyncCacheMiddleware(LocMemCache(), ttl=300)]
)
```

## Wrap framework-native caches behind Plynt's cache protocol

Any object that implements `get`, `set`, and `delete` with compatible
semantics can be used as a Plynt cache backend.

Example wrapper for Django's `django.core.cache`:

```python
from typing import Any


class DjangoCacheAdapter:
    def __init__(self, django_cache: Any) -> None:
        self._cache = django_cache

    def get(self, key: str) -> object | None:
        return self._cache.get(key)

    def set(self, key: str, value: object, ttl: float | None = None) -> None:
        timeout = None if ttl is None else int(ttl)
        self._cache.set(key, value, timeout=timeout)

    def delete(self, key: str) -> None:
        self._cache.delete(key)
```

Use this adapter exactly like built-in backends:

```python
from django.core.cache import caches
from plynt.middleware.cache import CacheMiddleware

cache_backend = DjangoCacheAdapter(caches["default"])
middleware = CacheMiddleware(cache_backend, ttl=300)
```

## Implement a custom cache backend

For non-framework systems, implement a small adapter class with the same three
methods.

```python
from collections.abc import MutableMapping


class DictCacheAdapter:
    def __init__(self, store: MutableMapping[str, object]) -> None:
        self._store = store

    def get(self, key: str) -> object | None:
        return self._store.get(key)

    def set(self, key: str, value: object, ttl: float | None = None) -> None:
        # This adapter ignores ttl; add expiry handling if needed.
        self._store[key] = value

    def delete(self, key: str) -> None:
        self._store.pop(key, None)
```

Start simple, then add TTL or eviction behavior only when your runtime needs
it.

## Reference

- All cache backends with full configuration options:
  [Cache backends reference](../reference/cache-backends.md).
