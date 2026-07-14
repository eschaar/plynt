# Django examples

Runnable snippets and integration patterns for using Plynth inside Django
applications.

## Available examples

- [Django cache backend](cache_backend.md) — build `HttpxSyncTransport` with
  `DjangoCacheBackend` and `CacheMiddleware`
- [Django transport from settings](transport_from_settings.md) — build
  `HttpxSyncTransport` or `HttpxAsyncTransport` via Django adapter helpers
- [Django middleware profile](middleware_profile.md) — align inbound Django
  middleware context with outbound plynth behavior

For DRF-specific examples, see
[../drf/README.md](../drf/README.md).

## Prerequisites

1. Install Django support:

```bash
pip install "plynth[django,httpx]"
```

1. Configure at least one cache alias in `settings.CACHES`.
1. Run the example from a Django-aware runtime (for example `manage.py shell`)
   so `django.core.cache` is importable.
