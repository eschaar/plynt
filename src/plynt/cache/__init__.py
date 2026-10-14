"""Cache backends and typed configuration for the HTTP transport layer.

All backends satisfy the ``CacheBackend`` protocol defined in
``plynt.base.cache`` and can be passed directly to ``CacheMiddleware``
or ``AsyncCacheMiddleware``.

Backends at a glance:

=================  ===  =====  ====  ===
Backend            TTL  Stats  Size  Notes
=================  ===  =====  ====  ===
``DummyCache``      no   no    no   Always a miss; useful as
                                    a disabled cache in tests.
``LocMemCache``     yes  yes   yes  Thread-safe, in-process.
                                    Uses ``time.monotonic`` for
                                    expiry.
``CachetoolsCache`` (1) yes   yes  Wraps any cachetools mapping
                                    (LRUCache, TTLCache, …).
                                    TTL is set on the cachetools
                                    cache, not per-key.
``RedisCache``      yes  yes   no   Wraps any Redis client.
                                    Serialises values with pickle.
=================  ===  =====  ====  ===

(1) Satisfies ``SupportsSizeInfo`` (``maxsize`` / ``currsize``).

Typed configuration (ADR-0010)
--------------------------------

Use the ``CacheConfig`` dataclasses to configure cache backends in an
``HTTPSettings`` subclass:

- ``DummyCacheConfig`` — no-op backend, no options.
- ``LocMemCacheConfig(max_size=1000)`` — in-process, thread-safe.
- ``RedisCacheConfig(location, key_prefix, socket_timeout, ...)``

Pass a config object to ``cache_from_config()`` to obtain the corresponding
``CacheBackend`` instance.

Example — typed configuration in a settings subclass::

    from plynt.cache import RedisCacheConfig
    from plynt.http.settings import HTTPSettings

    class MySettings(HTTPSettings):
        redis_url: str = ""

        @property
        def caches(self):
            if not self.redis_url:
                return None
            return {
                "responses": RedisCacheConfig(
                    location=self.redis_url,
                    key_prefix="myapp:http:",
                ),
            }

        @property
        def default_cache(self):
            return "responses"

Example — direct backend construction::

    from plynt.cache import LocMemCache
    from plynt.middleware.cache import CacheMiddleware
    from plynt.http.transport import HttpxSyncTransport

    transport = HttpxSyncTransport(
        middlewares=[CacheMiddleware(LocMemCache())],
    )

"""

from __future__ import annotations

from typing import Any

from plynt.base.cache import CacheBackend, CacheConfigBase
from plynt.cache.cachetools import CachetoolsCache
from plynt.cache.dummy import DummyCache, DummyCacheConfig
from plynt.cache.locmem import LocMemCache, LocMemCacheConfig
from plynt.cache.redis import RedisCache, RedisCacheConfig

__all__ = [
    "CacheConfig",
    "CacheConfigBase",
    "CachetoolsCache",
    "DummyCache",
    "DummyCacheConfig",
    "LocMemCache",
    "LocMemCacheConfig",
    "RedisCache",
    "RedisCacheConfig",
    "cache_from_config",
]

#: Union of all supported typed cache configuration objects.
#:
#: Pass one of these to ``cache_from_config()`` to obtain a ``CacheBackend``.
CacheConfig = LocMemCacheConfig | DummyCacheConfig | RedisCacheConfig


def cache_from_config(config: CacheConfig) -> CacheBackend:
    """Construct a ``CacheBackend`` from a typed ``CacheConfig`` object.

    This is the preferred factory when using the typed configuration API
    (ADR-0010).  It constructs the appropriate backend and wires all
    options declared on the config object.

    Supported config types:

    ===================  ==========================================
    Config type          Backend
    ===================  ==========================================
    ``DummyCacheConfig`` ``DummyCache`` (no-op)
    ``LocMemCacheConfig`` ``LocMemCache`` (in-process, thread-safe)
    ``RedisCacheConfig`` ``RedisCache`` (requires ``redis``)
    ===================  ==========================================

    Args:
        config: A typed cache configuration object.

    Returns:
        A ``CacheBackend`` instance configured according to *config*.

    Raises:
        ImportError: If ``RedisCacheConfig`` is used but the ``redis``
            package is not installed.

    Example::

        from plynt.cache import RedisCacheConfig, cache_from_config

        config = RedisCacheConfig(
            location="redis://localhost:6379/0",
            key_prefix="myapp:",
            socket_timeout=2.0,
        )
        backend = cache_from_config(config)

    """
    if isinstance(config, DummyCacheConfig):
        return DummyCache()
    if isinstance(config, LocMemCacheConfig):
        return LocMemCache()
    # RedisCacheConfig
    try:
        import redis as redis_lib
    except ImportError as exc:
        raise ImportError(
            "The 'redis' package is required for RedisCacheConfig. "
            "Install it with: pip install redis"
        ) from exc

    kwargs: dict[str, Any] = {}
    if config.socket_timeout is not None:
        kwargs["socket_timeout"] = config.socket_timeout
    if config.max_connections is not None:
        kwargs["max_connections"] = config.max_connections
    if config.retry_on_timeout:
        kwargs["retry_on_timeout"] = config.retry_on_timeout
    if config.ssl_certfile is not None:
        kwargs["ssl_certfile"] = config.ssl_certfile
    if config.ssl_keyfile is not None:
        kwargs["ssl_keyfile"] = config.ssl_keyfile
    if config.ssl_ca_certs is not None:
        kwargs["ssl_ca_certs"] = config.ssl_ca_certs

    client = redis_lib.from_url(config.location, **kwargs)
    return RedisCache(client, prefix=config.key_prefix)
