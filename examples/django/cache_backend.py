"""Django cache backend example for Plynth.

Shows how to reuse a Django cache alias with ``DjangoCacheBackend`` and
``CacheMiddleware``.
"""

from __future__ import annotations

from plynth.adapters.django.cache import DjangoCacheBackend
from plynth.base.middleware import SyncMiddleware
from plynth.http.transport import HttpxSyncTransport
from plynth.middleware.cache import CacheMiddleware


def build_transport_with_django_cache(alias: str = "default") -> HttpxSyncTransport:
    """Build a sync transport that caches responses via Django cache.

    Args:
        alias: Django cache alias defined in ``settings.CACHES``.

    Returns:
        Transport configured with response caching middleware.

    """
    cache_backend = DjangoCacheBackend(alias=alias)
    middlewares: list[SyncMiddleware] = []
    middlewares.append(CacheMiddleware(cache_backend, ttl=300))
    return HttpxSyncTransport(middlewares=middlewares)
