"""Tests for plynt.cache.dummy (DummyCache, DummyCacheConfig)."""

from __future__ import annotations

from plynt.base.cache import (
    CacheBackend,
    CacheConfigBase,
    SupportsSizeInfo,
    SupportsStats,
    SupportsTTL,
)
from plynt.cache import DummyCache, DummyCacheConfig


class TestDummyCache:
    """Test suite for DummyCache."""

    def test_satisfies_cache_backend_protocol(self) -> None:
        """Validate satisfies cache backend protocol."""
        assert isinstance(DummyCache(), CacheBackend)

    def test_does_not_satisfy_supports_ttl(self) -> None:
        """Validate does not satisfy supports ttl."""
        assert not isinstance(DummyCache(), SupportsTTL)

    def test_does_not_satisfy_supports_stats(self) -> None:
        """Validate does not satisfy supports stats."""
        assert not isinstance(DummyCache(), SupportsStats)

    def test_does_not_satisfy_supports_size_info(self) -> None:
        """Validate does not satisfy supports size info."""
        assert not isinstance(DummyCache(), SupportsSizeInfo)

    def test_get_always_returns_default(self) -> None:
        """Validate get always returns default."""
        cache = DummyCache()
        assert cache.get("any-key") is None
        assert cache.get("any-key", "fallback") == "fallback"

    def test_set_is_noop(self) -> None:
        """Validate set is noop."""
        cache = DummyCache()
        cache.set("k", "v")
        assert cache.get("k") is None

    def test_delete_is_noop(self) -> None:
        """Validate delete is noop."""
        cache = DummyCache()
        cache.delete("k")  # must not raise

    def test_clear_is_noop(self) -> None:
        """Validate clear is noop."""
        cache = DummyCache()
        cache.clear()  # must not raise

    def test_set_with_ttl_is_noop(self) -> None:
        """Validate set with ttl is noop."""
        cache = DummyCache()
        cache.set("k", "v", ttl=60.0)
        assert cache.get("k") is None


class TestDummyCacheConfig:
    """Tests for DummyCacheConfig (ADR-0010)."""

    def test_is_instance_of_cache_config_base(self) -> None:
        """Validate is instance of cache config base."""
        assert isinstance(DummyCacheConfig(), CacheConfigBase)

    def test_instantiates_with_no_args(self) -> None:
        """Validate instantiates with no args."""
        config = DummyCacheConfig()
        assert isinstance(config, DummyCacheConfig)

    def test_equality(self) -> None:
        """Validate equality."""
        assert DummyCacheConfig() == DummyCacheConfig()
