# Cache backends reference

Plynth's `CacheBackend` protocol is defined in `plynth.base.cache`. Any
class that implements `get`, `set`, and `delete` is a valid backend.

## LocMemCache

**Module:** `plynth.cache.locmem`

In-process, thread-safe dictionary cache. No external dependencies.
Suitable for a single process.

```python
from plynth.cache import LocMemCache

cache = LocMemCache()
cache.set("key", value)             # no expiry
cache.set("key", value, ttl=300.0)  # expire after 5 minutes
value = cache.get("key")            # None on miss
cache.delete("key")
cache.clear()                        # remove all entries
```

**Trade-offs:**

- Not shared across processes or workers.
- All data is lost when the process restarts.
- TTL is checked at read time; no background eviction thread.

______________________________________________________________________

## RedisCache

**Module:** `plynth.cache.redis`

Stores entries in Redis using `pickle` serialisation.
Suitable for multi-process deployments.

```python
import redis
from plynth.cache import RedisCache

client = redis.Redis(host="localhost", port=6379, db=0)
cache = RedisCache(client, prefix="my-service:")
```

| Parameter | Type          | Default     | Description                       |
| --------- | ------------- | ----------- | --------------------------------- |
| `client`  | `redis.Redis` | required    | A connected Redis client instance |
| `prefix`  | `str`         | `"plynth:"` | Key namespace prefix              |

**Security note:** `RedisCache` serialises with `pickle`. Ensure the Redis
instance is accessible only from trusted processes — do not expose it to
untrusted input.

______________________________________________________________________

## CachetoolsCache

**Module:** `plynth.cache.cachetools`

Wraps any `cachetools` mapping (e.g. `LRUCache`, `TTLCache`).
Use this when you need eviction by size or time within a single process.

```python
from cachetools import LRUCache, TTLCache
from plynth.cache import CachetoolsCache

# Evict by size
lru = CachetoolsCache(LRUCache(maxsize=256))

# Evict by time (cachetools TTLCache)
ttl = CachetoolsCache(TTLCache(maxsize=256, ttl=300))
```

`CachetoolsCache` requires the `cachetools` package:

```bash
pip install cachetools
```

______________________________________________________________________

## DummyCache

**Module:** `plynth.cache.dummy`

Always misses — `get` always returns `None`, `set` and `delete` are
no-ops. Use in tests to disable caching without changing application code.

```python
from plynth.cache import DummyCache

cache = DummyCache()
```

______________________________________________________________________

## Choosing a backend

| Situation                                           | Recommended backend |
| --------------------------------------------------- | ------------------- |
| Single process, small dataset                       | `LocMemCache`       |
| Single process, bounded size or time-based eviction | `CachetoolsCache`   |
| Multiple processes or workers                       | `RedisCache`        |
| Tests                                               | `DummyCache`        |

## Using a backend with CacheMiddleware

Pass the backend directly. TTL is configured on `CacheMiddleware` via the
`ttl` parameter, which is forwarded to `backend.set()` on each write:

```python
from plynth.middleware.cache import CacheMiddleware
from plynth.cache import LocMemCache

CacheMiddleware(LocMemCache(), ttl=300)
```

See [How to use caching](../how-to/use-cache.md) for placement in the
middleware stack.
