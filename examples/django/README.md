# Django examples

Runnable snippets and integration patterns for using Plynth inside Django
applications.

## Available examples

- [Django cache backend](cache_backend.py) — build `HttpxSyncTransport` with
  `DjangoCacheBackend` and `CacheMiddleware`

## Prerequisites

1. Install Django support:

```bash
pip install "plynth[django,httpx]"
```

1. Configure at least one cache alias in `settings.CACHES`.
1. Run the example from a Django-aware runtime (for example `manage.py shell`)
   so `django.core.cache` is importable.
