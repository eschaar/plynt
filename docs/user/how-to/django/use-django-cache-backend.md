# How to use Django cache with Plynt

Use `DjangoCacheBackend` when a Django service already has cache aliases
configured in `settings.py` and you want Plynt response caching without
building a custom adapter.

## Install extras

```bash
pip install "plynt[django,httpx]"
```

## Configure Django cache aliases

Define at least one alias in Django `CACHES`.

```python
# settings.py
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "plynt-default",
    },
    "plynt_api": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "plynt-api",
    },
}
```

## Build transport with Django cache backend

```python
from plynt.adapters.django.cache import DjangoCacheBackend
from plynt.http.transport import HttpxSyncTransport
from plynt.middleware.cache import CacheMiddleware

cache_backend = DjangoCacheBackend(alias="plynt_api")
transport = HttpxSyncTransport(middlewares=[CacheMiddleware(cache_backend, ttl=300)])
```

## What is stored in cache

When a response is cached, `DjangoCacheBackend` stores an explicit payload:

1. `schema_version` for compatibility checks
1. `kind` marker (`plynt.response`)
1. `status_code`
1. `headers`
1. `content_b64` (base64-encoded response bytes)

Corrupt or unknown payloads fail closed: `get(...)` returns your `default`
value instead of raising.

## End-to-end usage pattern

```python
from plynt.adapters.django.cache import DjangoCacheBackend
from plynt.http.client import APIClient
from plynt.http.transport import HttpxSyncTransport
from plynt.middleware.cache import CacheMiddleware

cache_backend = DjangoCacheBackend(alias="plynt_api")
transport = HttpxSyncTransport(middlewares=[CacheMiddleware(cache_backend, ttl=120)])
client = APIClient(base_url="https://api.example.com", transport=transport)

response = client.get("/products")
response.raise_for_status()
```

## Notes

1. Alias lookup happens at runtime through `django.core.cache.caches`.
1. `ttl` is converted to Django `timeout` semantics.
1. Negative TTL values are clamped to `0`.
1. `ttl=None` uses Django backend defaults.

## Next step

If you also want settings-driven auth + retry + cache wiring in one call, see
[How to build a transport from Django settings](use-django-transport-helper.md).
