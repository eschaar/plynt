# Add response caching

This tutorial adds `CacheMiddleware` to the connector built in
[Tutorial 2](02-build-a-connector.md), starting with an in-memory cache
and then switching to Redis for multi-process deployments.

## How caching works in Plynth

`CacheMiddleware` is a transport-level middleware. It:

- Caches `GET` responses only (other methods always pass through).
- Uses a `CacheBackend` you provide — no backend is built-in.
- Returns a cached `Response` without making a network call on a hit.
- Stores the response on a miss.

Because it runs inside the transport, caching applies to *all* services
that share that transport — no per-service configuration needed.

## Step 1 — Add in-memory caching

`LocMemCache` stores responses in a Python `dict` inside the current
process. It is fast and requires no external dependencies.

```python
from plynth.cache import LocMemCache
from plynth.middleware.cache import CacheMiddleware
from plynth.http.transport import HttpxSyncTransport

cache = LocMemCache()

transport = HttpxSyncTransport(
    middlewares=[
        CacheMiddleware(cache, ttl=300),
    ]
)
```

The `ttl` argument controls how long a cached response is considered fresh.
`300` means five minutes. Pass `ttl=None` (the default) to let the backend
decide — `LocMemCache` never expires entries unless you configure it to.

Put `CacheMiddleware` **outermost** so that a cache hit skips auth token
fetching, retry logic, and network I/O.

## Step 2 — Switch to Redis for multi-process deployments

`LocMemCache` is not shared across processes or workers. Use `RedisCache`
when you run multiple workers or need cache entries to survive restarts.

```python
import redis
from plynth.cache import RedisCache
from plynth.middleware.cache import CacheMiddleware

redis_client = redis.Redis(host="localhost", port=6379, db=0)
cache = RedisCache(redis_client, prefix="issues:")

transport = HttpxSyncTransport(
    middlewares=[
        CacheMiddleware(cache, ttl=600),
    ]
)
```

`RedisCache` serialises responses with `pickle`. Ensure your Redis instance
is secured — see the security note in
[Cache backends reference](../reference/cache-backends.md).

## Step 3 — Choosing a TTL

`CacheMiddleware` passes `ttl` directly to `backend.set()` on every cache
write. The backend decides how to honour it:

| Backend                          | TTL support                                   |
| -------------------------------- | --------------------------------------------- |
| `LocMemCache`                    | Evicts at read time if expired                |
| `RedisCache`                     | Sets Redis `EXPIRE` when `ttl` is given       |
| `CachetoolsCache(TTLCache(...))` | TTL configured on the cachetools cache itself |
| `DummyCache`                     | Ignores TTL (always misses)                   |

Use `ttl=None` only if you are managing expiry through the backend
directly (for example `TTLCache(maxsize=..., ttl=...)`). When in doubt,
set an explicit TTL on the middleware.

## Step 4 — Use LRU caching with cachetools

`CachetoolsCache` wraps any cachetools mapping. Use it for LRU or TTL
eviction with a size limit:

```python
from cachetools import LRUCache
from plynth.cache import CachetoolsCache
from plynth.middleware.cache import CacheMiddleware

cache = CachetoolsCache(LRUCache(maxsize=256))

transport = HttpxSyncTransport(
    middlewares=[CacheMiddleware(cache, ttl=300)],
)
```

## Step 5 — Combine caching with other middleware

```python
from plynth.cache import LocMemCache
from plynth.middleware.cache import CacheMiddleware
from plynth.middleware.logging import LoggingMiddleware
from plynth.middleware.retry import RetryMiddleware
from plynth.http.policies import HttpRetryPolicy
from plynth.http.auth import auth_from_config

cache = LocMemCache()

middlewares = [
    CacheMiddleware(cache, ttl=300),   # outermost — cache hit skips everything
    LoggingMiddleware(),
]

if settings.auth:
    middlewares.append(auth_from_config(settings.auth))

middlewares.append(
    RetryMiddleware(HttpRetryPolicy(max_attempts=3, retryable_status_codes={503}))
)

transport = HttpxSyncTransport(middlewares=middlewares)
```

## Async

Use `AsyncCacheMiddleware` with `HttpxAsyncTransport`. The backend
(`LocMemCache`, `RedisCache`, etc.) is the same — no async-specific
backend is needed.

```python
from plynth.middleware.cache import AsyncCacheMiddleware

transport = HttpxAsyncTransport(
    middlewares=[AsyncCacheMiddleware(LocMemCache(), ttl=300)]
)
```

## Next steps

- [Test with VCR](05-test-with-vcr.md) — record and replay HTTP
  interactions in tests without real network calls.
- [Cache backends reference](../reference/cache-backends.md) — all
  available backends, configuration options, and trade-offs.
