"""Tests for plynt.cache.cachetools (CachetoolsCache)."""

from __future__ import annotations

from typing import Any

from plynt.base.cache import (
    CacheBackend,
    SupportsSizeInfo,
    SupportsStats,
    SupportsTTL,
)
from plynt.cache import CachetoolsCache


class _FakeCachetoolsCache:
    """Minimal mapping that mimics the cachetools.Cache interface."""

    def __init__(self, maxsize: int = 128) -> None:
        """Initialize _FakeCachetoolsCache."""
        self._store: dict[str, Any] = {}
        self.maxsize = maxsize

    @property
    def currsize(self) -> int:
        """Return currsize."""
        return len(self._store)

    def get(self, key: str, default: Any = None) -> Any:
        """Return get."""
        return self._store.get(key, default)

    def __setitem__(self, key: str, value: Any) -> None:
        """Handle setitem."""
        self._store[key] = value

    def __delitem__(self, key: str) -> None:
        """Handle delitem."""
        del self._store[key]

    def clear(self) -> None:
        """Return clear."""
        self._store.clear()


class TestCachetoolsCache:
    """Test suite for CachetoolsCache."""

    def _make(self) -> CachetoolsCache:
        """Handle make."""
        return CachetoolsCache(_FakeCachetoolsCache(maxsize=64))

    def test_satisfies_cache_backend_protocol(self) -> None:
        """Validate satisfies cache backend protocol."""
        assert isinstance(self._make(), CacheBackend)

    def test_satisfies_supports_size_info_protocol(self) -> None:
        """Validate satisfies supports size info protocol."""
        assert isinstance(self._make(), SupportsSizeInfo)

    def test_does_not_satisfy_supports_ttl(self) -> None:
        """Validate does not satisfy supports ttl."""
        assert not isinstance(self._make(), SupportsTTL)

    def test_does_not_satisfy_supports_stats(self) -> None:
        """Validate does not satisfy supports stats."""
        assert not isinstance(self._make(), SupportsStats)

    def test_set_and_get_roundtrip(self) -> None:
        """Validate set and get roundtrip."""
        backend = self._make()
        backend.set("k", "value")
        assert backend.get("k") == "value"

    def test_get_missing_returns_default(self) -> None:
        """Validate get missing returns default."""
        backend = self._make()
        assert backend.get("missing") is None
        assert backend.get("missing", "fallback") == "fallback"

    def test_delete_removes_entry(self) -> None:
        """Validate delete removes entry."""
        backend = self._make()
        backend.set("k", "v")
        backend.delete("k")
        assert backend.get("k") is None

    def test_delete_missing_key_is_noop(self) -> None:
        """Validate delete missing key is noop."""
        backend = self._make()
        backend.delete("absent")  # must not raise

    def test_clear_empties_cache(self) -> None:
        """Validate clear empties cache."""
        backend = self._make()
        backend.set("a", 1)
        backend.set("b", 2)
        backend.clear()
        assert backend.get("a") is None

    def test_ttl_is_ignored_on_set(self) -> None:
        """Validate ttl is ignored on set."""
        backend = self._make()
        backend.set("k", "v", ttl=60.0)  # ttl silently ignored
        assert backend.get("k") == "v"

    def test_maxsize_exposes_underlying_maxsize(self) -> None:
        """Validate maxsize exposes underlying maxsize."""
        backend = self._make()
        assert backend.maxsize == 64

    def test_currsize_reflects_stored_entries(self) -> None:
        """Validate currsize reflects stored entries."""
        backend = self._make()
        assert backend.currsize == 0
        backend.set("k", "v")
        assert backend.currsize == 1
