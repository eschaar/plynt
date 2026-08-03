"""Cache backend protocol and capability protocols for Plynth.

Defines:

- ``CacheBackend`` — the minimal protocol all cache backends must satisfy.
- ``SupportsTTL``, ``SupportsStats``, ``SupportsSizeInfo`` — optional
  capability protocols for richer backends.

Cache middleware implementations (``CacheMiddleware``, ``AsyncCacheMiddleware``)
live in ``plynth.middleware.cache``.

**Core interface** (all backends must implement):

.. code-block:: python

    backend.get(key, default=None)  # return cached value or default
    backend.set(key, value, ttl=None)  # store; ttl may be ignored
    backend.delete(key)             # remove one entry
    backend.clear()                 # remove all entries

**Optional capabilities** — check with ``isinstance`` before using:

.. code-block:: python

    if isinstance(backend, SupportsTTL):
        print(backend.ttl("my-key"))  # remaining seconds

    if isinstance(backend, SupportsStats):
        print(backend.stats())

    if isinstance(backend, SupportsSizeInfo):
        print(backend.maxsize, backend.currsize)

**Concrete backends** live in ``plynth.cache``:
``DummyCache``, ``LocMemCache``, ``CachetoolsCache``, ``RedisCache``.

Usage::

    from plynth.middleware.cache import CacheMiddleware
    from plynth.cache import LocMemCache
    from plynth.http.transport import HttpxSyncTransport

    transport = HttpxSyncTransport(
        middlewares=[CacheMiddleware(LocMemCache())],
    )

"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable
from urllib.parse import urlencode

from plynth.base.request import Request

__all__ = [
    "CacheBackend",
    "CacheConfigBase",
    "SupportsSizeInfo",
    "SupportsStats",
    "SupportsTTL",
]

# Headers that can change the effective response representation and should
# therefore contribute to cache-key partitioning.
_CACHE_KEY_VARY_HEADERS: frozenset[str] = frozenset(
    {
        "accept",
        "accept-language",
        "authorization",
    }
)


# ---------------------------------------------------------------------------
# Config marker
# ---------------------------------------------------------------------------


@dataclass
class CacheConfigBase:
    """Marker base for all typed cache configuration dataclasses.

    Inheriting from this class allows consumer code to use
    ``isinstance(cfg, CacheConfigBase)`` to verify that an object is a
    recognised cache configuration, regardless of which specific backend
    it targets.

    This class carries no fields or behaviour.  All configuration is
    defined by the concrete subclass.

    Example::

        from plynth.base.cache import CacheConfigBase

        def validate_cache_cfg(cfg: object) -> None:
            if not isinstance(cfg, CacheConfigBase):
                raise TypeError(f"Expected a CacheConfig, got {type(cfg)!r}")

    """


# ---------------------------------------------------------------------------
# Core protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class CacheBackend(Protocol):
    """Minimal protocol that all cache backends must satisfy.

    The four core operations are deliberately kept small so that any
    backend — in-process dict, Redis, memcached, database — can implement
    them without special dependencies.

    TTL support is optional: if a backend cannot honour ``ttl``, it may
    ignore the parameter.  Callers that care about TTL should verify the
    backend also satisfies ``SupportsTTL``.

    Example — minimal in-memory backend::

        class SimpleCache:
            def __init__(self) -> None:
                self._store: dict[str, Any] = {}

            def get(self, key: str, default: Any = None) -> Any:
                return self._store.get(key, default)

            def set(
                self, key: str, value: Any, ttl: float | None = None
            ) -> None:
                self._store[key] = value  # ttl ignored

            def delete(self, key: str) -> None:
                self._store.pop(key, None)

            def clear(self) -> None:
                self._store.clear()

    """

    def get(self, key: str, default: Any = None) -> Any:
        """Return the cached value for *key*, or *default* if absent."""
        raise NotImplementedError

    def set(self, key: str, value: Any, ttl: float | None = None) -> None:
        """Store *value* under *key*.

        Args:
            key: Cache key.
            value: Value to store.
            ttl: Time-to-live in seconds. Backends that do not support
                per-key TTL may ignore this parameter.

        """
        raise NotImplementedError

    def delete(self, key: str) -> None:
        """Remove the entry for *key*.  No-op if the key is absent."""
        raise NotImplementedError

    def clear(self) -> None:
        """Remove all entries from the cache."""
        raise NotImplementedError

    @staticmethod
    def cache_key(request: Request) -> str:
        """Build a stable, collision-resistant cache key from a request.

        The key is a SHA-256 hex digest of the canonical request
        representation: ``METHOD URL?param1=val1&param2=val2|h=v...``.
        Query parameters are sorted alphabetically for stability regardless
        of insertion order. A small allowlist of representation/auth-related
        headers is included to avoid cache collisions across different
        authorization or content-negotiation contexts.

        Returns:
            A 64-character lowercase SHA-256 hex digest.

        """
        canonical = f"{request.method.upper()} {request.url}"
        if request.params:
            qs = urlencode(sorted(request.params.items()))
            canonical = f"{canonical}?{qs}"

        if request.headers:
            lower_headers = {k.lower(): v for k, v in request.headers.items()}
            vary_parts: list[str] = []
            for name in sorted(_CACHE_KEY_VARY_HEADERS):
                value = lower_headers.get(name)
                if value is not None:
                    vary_parts.append(f"{name}={value}")
            if vary_parts:
                canonical = f"{canonical}|{'&'.join(vary_parts)}"
        return hashlib.sha256(canonical.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Optional capability protocols
# ---------------------------------------------------------------------------


@runtime_checkable
# pylint: disable=too-few-public-methods
class SupportsTTL(Protocol):
    """Optional capability: per-key TTL inspection.

    Backends that manage expiry internally (e.g. ``LocMemCache``,
    ``RedisCache``) should implement this.
    """

    def ttl(self, key: str) -> float | None:
        """Return remaining TTL in seconds for *key*.

        Returns:
            Remaining seconds, ``0.0`` if the key is expired but not yet
            evicted, or ``None`` if the key has no expiry (permanent).

        """
        raise NotImplementedError


@runtime_checkable
# pylint: disable=too-few-public-methods
class SupportsStats(Protocol):
    """Optional capability: backend statistics.

    Implement when the underlying backend can report metrics (hit/miss
    counts, memory usage, etc.).
    """

    def stats(self) -> dict[str, Any]:
        """Return a snapshot of backend statistics.

        The keys and their meaning are backend-specific.  Common keys
        include ``currsize``, ``maxsize``, ``keyspace_hits``, and
        ``used_memory_human``.

        """
        raise NotImplementedError


@runtime_checkable
class SupportsSizeInfo(Protocol):
    """Optional capability: size and eviction metadata.

    Typically satisfied by in-memory caches that have a bounded size
    (e.g. LRU, LFU).  Unbounded backends may expose ``maxsize = None``.

    Both attributes are read-only — implementations may use a plain class
    attribute or a ``@property``.
    """

    @property
    def maxsize(self) -> int | None:
        """Maximum number of entries, or ``None`` if unbounded."""
        raise NotImplementedError

    @property
    def currsize(self) -> int:
        """Current number of stored entries."""
        raise NotImplementedError
