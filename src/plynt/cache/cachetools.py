"""Cachetools adapter cache backend.

``CachetoolsCache`` wraps any cachetools mapping (``LRUCache``,
``TTLCache``, ``LFUCache``, …) and adapts it to the ``CacheBackend``
protocol.

Requires ``pip install cachetools``.
"""

from __future__ import annotations

from typing import Any

from plynt.base.cache import CacheBackend, SupportsSizeInfo


class CachetoolsCache(CacheBackend, SupportsSizeInfo):
    """Adapts a cachetools mapping to the ``CacheBackend`` protocol.

    Cachetools caches (``LRUCache``, ``TTLCache``, ``LFUCache``, …) are
    mapping-like objects with ``maxsize`` and ``currsize`` attributes.
    This adapter wraps them so they can be used with ``CacheMiddleware``.

    TTL is configured on the cachetools cache constructor (e.g. via
    ``TTLCache(maxsize=..., ttl=...)``), **not** per-key via
    ``CacheBackend.set(ttl=…)``.  The *ttl* parameter of ``set`` is
    silently ignored.

    Satisfies ``CacheBackend`` and ``SupportsSizeInfo``.

    Requires ``pip install cachetools``.

    Example::

        from cachetools import LRUCache
        from plynt.cache import CachetoolsCache

        backend = CachetoolsCache(LRUCache(maxsize=256))

    Args:
        cache: A cachetools cache instance (or any compatible mapping with
            ``get``, ``__setitem__``, ``__delitem__``, ``clear``,
            ``maxsize``, and ``currsize`` attributes).

    """

    def __init__(self, cache: Any) -> None:
        """Initialize CachetoolsCache."""
        self._cache = cache

    def get(self, key: str, default: Any = None) -> Any:
        """Return the cached value for *key*, or *default* if absent."""
        return self._cache.get(key, default)

    def set(self, key: str, value: Any, ttl: float | None = None) -> None:
        """Store *value* under *key*.  *ttl* is ignored (set on the cache)."""
        self._cache[key] = value

    def delete(self, key: str) -> None:
        """Remove *key*.  No-op if the key is absent."""
        try:
            del self._cache[key]
        except KeyError:
            pass

    def clear(self) -> None:
        """Remove all entries."""
        self._cache.clear()

    @property
    def maxsize(self) -> int | None:
        """Maximum number of entries allowed by the underlying cache."""
        return self._cache.maxsize  # type: ignore[no-any-return]

    @property
    def currsize(self) -> int:
        """Current number of stored entries."""
        return self._cache.currsize  # type: ignore[no-any-return]
