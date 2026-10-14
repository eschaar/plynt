"""Dummy (no-op) cache backend and its typed configuration.

Use ``DummyCache`` when you want to pass a cache to code that requires one
without actually caching anything — useful in tests or as a disabled-cache
placeholder that keeps the transport stack unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from plynt.base.cache import CacheBackend, CacheConfigBase


class DummyCache(CacheBackend):
    """No-op cache backend — every read is a miss, every write is dropped.

    Useful as a disabled-cache placeholder in tests or when you want to
    run code that accepts a cache without actually caching anything.

    Example::

        from plynt.cache import DummyCache
        from plynt.middleware.cache import CacheMiddleware
        from plynt.http.transport import HttpxSyncTransport

        transport = HttpxSyncTransport(
            middlewares=[CacheMiddleware(DummyCache())],
        )

    """

    def get(self, key: str, default: Any = None) -> Any:
        """Always return *default*."""
        return default

    def set(self, key: str, value: Any, ttl: float | None = None) -> None:
        """No-op."""

    def delete(self, key: str) -> None:
        """No-op."""

    def clear(self) -> None:
        """No-op."""


@dataclass
class DummyCacheConfig(CacheConfigBase):
    """Configuration for the no-op ``DummyCache`` backend.

    No-op cache backend: every read is a miss, every write is dropped.
    Useful in tests or when you want to disable caching without removing
    it from the transport stack.

    Example::

        from plynt.cache import DummyCacheConfig

        class MySettings(HTTPSettings):
            @property
            def caches(self) -> dict[str, CacheConfig] | None:
                return {"default": DummyCacheConfig()}

    """
