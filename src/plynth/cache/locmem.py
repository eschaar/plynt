"""In-process, thread-safe cache backend and its typed configuration.

``LocMemCache`` stores values in a plain Python dict behind a threading
lock.  It is not shared across workers or processes — use ``RedisCache``
for shared caching.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any

from plynth.base.cache import (
    CacheBackend,
    CacheConfigBase,
    SupportsSizeInfo,
    SupportsStats,
    SupportsTTL,
)


class LocMemCache(CacheBackend, SupportsTTL, SupportsStats, SupportsSizeInfo):
    """Thread-safe in-process cache with optional per-key TTL.

    Values are stored in a plain Python dict.  Expired entries are evicted
    lazily on ``get``; call ``purge_expired()`` to force a sweep.

    Satisfies ``CacheBackend``, ``SupportsTTL``, ``SupportsStats``,
    and ``SupportsSizeInfo``.

    This backend is in-process only — it is **not** shared across
    workers, threads (beyond thread safety of individual operations), or
    processes.  Use ``RedisCache`` for a shared cache.

    Example::

        from plynth.cache import LocMemCache

        cache = LocMemCache()
        cache.set("key", response, ttl=300)  # expires in 5 minutes
        value = cache.get("key")

    """

    maxsize: int | None = None  # unlimited

    def __init__(self) -> None:
        # _store maps key → (value, expires_at) where expires_at is a
        # monotonic timestamp or None for no expiry.
        """Initialize LocMemCache."""
        self._store: dict[str, tuple[Any, float | None]] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # CacheBackend core
    # ------------------------------------------------------------------

    def get(self, key: str, default: Any = None) -> Any:
        """Return the cached value for *key*, or *default* if absent/expired.

        Expired entries are evicted on access.

        Args:
            key: Cache key.
            default: Returned when the key is absent or expired.

        """
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return default
            value, expires_at = entry
            if expires_at is not None and time.monotonic() >= expires_at:
                del self._store[key]
                return default
            return value

    def set(self, key: str, value: Any, ttl: float | None = None) -> None:
        """Store *value* under *key*, optionally expiring after *ttl* seconds.

        Args:
            key: Cache key.
            value: Value to store.
            ttl: Time-to-live in seconds, or ``None`` for no expiry.

        """
        expires_at = time.monotonic() + ttl if ttl is not None else None
        with self._lock:
            self._store[key] = (value, expires_at)

    def delete(self, key: str) -> None:
        """Remove *key*.  No-op if the key is absent.

        Args:
            key: Cache key to remove.

        """
        with self._lock:
            self._store.pop(key, None)

    def clear(self) -> None:
        """Remove all entries, including unexpired ones."""
        with self._lock:
            self._store.clear()

    # ------------------------------------------------------------------
    # SupportsTTL
    # ------------------------------------------------------------------

    def ttl(self, key: str) -> float | None:
        """Return remaining TTL in seconds for *key*.

        Returns:
            Remaining seconds, ``0.0`` if the entry is expired but not
            yet evicted, or ``None`` if the key has no expiry or is
            absent.

        """
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            _, expires_at = entry
            if expires_at is None:
                return None
            return max(0.0, expires_at - time.monotonic())

    # ------------------------------------------------------------------
    # SupportsStats
    # ------------------------------------------------------------------

    def stats(self) -> dict[str, Any]:
        """Return a snapshot of cache statistics.

        Returns a dict with ``currsize`` (live entries, i.e. not yet
        expired) and ``maxsize`` (always ``None`` for this backend).

        """
        with self._lock:
            now = time.monotonic()
            live = sum(
                1
                for _, expires_at in self._store.values()
                if expires_at is None or now < expires_at
            )
        return {"currsize": live, "maxsize": None}

    # ------------------------------------------------------------------
    # SupportsSizeInfo
    # ------------------------------------------------------------------

    @property
    def currsize(self) -> int:
        """Current number of stored entries (including expired but unevicted)."""
        with self._lock:
            return len(self._store)

    # ------------------------------------------------------------------
    # Extras
    # ------------------------------------------------------------------

    def purge_expired(self) -> int:
        """Remove all expired entries and return the number removed.

        ``get`` evicts entries lazily; call this to proactively reclaim
        memory.

        Returns:
            Number of entries removed.

        """
        now = time.monotonic()
        with self._lock:
            expired = [
                k
                for k, (_, exp) in self._store.items()
                if exp is not None and now >= exp
            ]
            for k in expired:
                del self._store[k]
        return len(expired)


@dataclass
class LocMemCacheConfig(CacheConfigBase):
    """Configuration for the in-process ``LocMemCache`` backend.

    Thread-safe, in-process cache.  Not shared across workers or
    processes.  Use ``RedisCacheConfig`` for a shared cache.

    Args:
        max_size: Maximum number of entries.  Currently informational
            only — ``LocMemCache`` is unbounded by default.  Reserved
            for future use.

    Example::

        from plynth.cache import LocMemCacheConfig

        class MySettings(HTTPSettings):
            @property
            def caches(self) -> dict[str, CacheConfig] | None:
                return {"default": LocMemCacheConfig(max_size=500)}

    """

    max_size: int = 1000
