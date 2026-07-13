# How to use Django cache with Plynth

Use `DjangoCacheBackend` when a Django service already has cache aliases
configured in `settings.py` and you want Plynth response caching without
building a custom adapter.

## Install extras

```bash
pip install "plynth[django,httpx]"
```

## Configure Django cache aliases

Define at least one alias in Django `CACHES`.

```python
# settings.py
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "plynth-default",
    },
    "plynth_api": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "plynth-api",
    },
}
```

## Build transport with Django cache backend

```python
from plynth.adapters.django.cache import DjangoCacheBackend
from plynth.http.transport import HttpxSyncTransport
from plynth.middleware.cache import CacheMiddleware

cache_backend = DjangoCacheBackend(alias="plynth_api")
transport = HttpxSyncTransport(
    middlewares=[CacheMiddleware(cache_backend, ttl=300)]
)
```

## What is stored in cache

When a response is cached, `DjangoCacheBackend` stores an explicit payload:

1. `schema_version` for compatibility checks
1. `kind` marker (`plynth.response`)
1. `status_code`
1. `headers`
1. `content_b64` (base64-encoded response bytes)

Corrupt or unknown payloads fail closed: `get(...)` returns your `default`
value instead of raising.

## End-to-end usage pattern

```python
from plynth.adapters.django.cache import DjangoCacheBackend
from plynth.http.client import APIClient
from plynth.http.transport import HttpxSyncTransport
from plynth.middleware.cache import CacheMiddleware

cache_backend = DjangoCacheBackend(alias="plynth_api")
transport = HttpxSyncTransport(
    middlewares=[CacheMiddleware(cache_backend, ttl=120)]
)
client = APIClient(base_url="https://api.example.com", transport=transport)

response = client.get("/products")
response.raise_for_status()
```

## Notes

1. Alias lookup happens at runtime through `django.core.cache.caches`.
1. `ttl` is converted to Django `timeout` semantics.
1. Negative TTL values are clamped to `0`.
1. `ttl=None` uses Django backend defaults.
