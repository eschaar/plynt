# Django examples

Runnable snippets and integration patterns for using Plynth inside Django
applications.

## Available examples

- [Django cache backend](cache_backend.md) — build `HttpxSyncTransport` with
  `DjangoCacheBackend` and `CacheMiddleware`
- [Django transport from settings](transport_from_settings.md) — build
  `HttpxSyncTransport` via `transport_from_django_settings`
- [DRF service view](drf_service_view.md) — configure `PlynthServiceMixin`
  with named service factories

## Prerequisites

1. Install Django support:

```bash
pip install "plynth[django,httpx]"
```

1. Configure at least one cache alias in `settings.CACHES`.
1. Run the example from a Django-aware runtime (for example `manage.py shell`)
   so `django.core.cache` is importable.
