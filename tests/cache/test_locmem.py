"""Tests for plynth.cache.locmem (LocMemCache, LocMemCacheConfig)."""

from __future__ import annotations

import time

from plynth.base.cache import (
    CacheBackend,
    CacheConfigBase,
    SupportsSizeInfo,
    SupportsStats,
    SupportsTTL,
)
from plynth.cache import LocMemCache, LocMemCacheConfig


class TestLocMemCache:
    """Test suite for LocMemCache."""

    def test_satisfies_cache_backend_protocol(self) -> None:
        """Validate satisfies cache backend protocol."""
        assert isinstance(LocMemCache(), CacheBackend)

    def test_satisfies_supports_ttl_protocol(self) -> None:
        """Validate satisfies supports ttl protocol."""
        assert isinstance(LocMemCache(), SupportsTTL)

    def test_satisfies_supports_stats_protocol(self) -> None:
        """Validate satisfies supports stats protocol."""
        assert isinstance(LocMemCache(), SupportsStats)

    def test_satisfies_supports_size_info_protocol(self) -> None:
        """Validate satisfies supports size info protocol."""
        assert isinstance(LocMemCache(), SupportsSizeInfo)

    def test_maxsize_is_none(self) -> None:
        """Validate maxsize is none."""
        assert LocMemCache().maxsize is None

    def test_set_and_get_roundtrip(self) -> None:
        """Validate set and get roundtrip."""
        cache = LocMemCache()
        cache.set("k", "hello")
        assert cache.get("k") == "hello"

    def test_get_missing_returns_default(self) -> None:
        """Validate get missing returns default."""
        cache = LocMemCache()
        assert cache.get("missing") is None
        assert cache.get("missing", 42) == 42

    def test_delete_removes_entry(self) -> None:
        """Validate delete removes entry."""
        cache = LocMemCache()
        cache.set("k", "v")
        cache.delete("k")
        assert cache.get("k") is None

    def test_delete_missing_key_is_noop(self) -> None:
        """Validate delete missing key is noop."""
        cache = LocMemCache()
        cache.delete("nonexistent")  # must not raise

    def test_clear_removes_all(self) -> None:
        """Validate clear removes all."""
        cache = LocMemCache()
        cache.set("a", 1)
        cache.set("b", 2)
        cache.clear()
        assert cache.get("a") is None
        assert cache.get("b") is None
        assert cache.currsize == 0

    def test_currsize_reflects_stored_entries(self) -> None:
        """Validate currsize reflects stored entries."""
        cache = LocMemCache()
        assert cache.currsize == 0
        cache.set("a", 1)
        assert cache.currsize == 1
        cache.set("b", 2)
        assert cache.currsize == 2
        cache.delete("a")
        assert cache.currsize == 1

    def test_overwrite_existing_key(self) -> None:
        """Validate overwrite existing key."""
        cache = LocMemCache()
        cache.set("k", "first")
        cache.set("k", "second")
        assert cache.get("k") == "second"

    def test_ttl_none_when_no_expiry(self) -> None:
        """Validate ttl none when no expiry."""
        cache = LocMemCache()
        cache.set("k", "v")  # no TTL
        assert cache.ttl("k") is None

    def test_ttl_none_for_absent_key(self) -> None:
        """Validate ttl none for absent key."""
        cache = LocMemCache()
        assert cache.ttl("missing") is None

    def test_ttl_returns_positive_seconds(self) -> None:
        """Validate ttl returns positive seconds."""
        cache = LocMemCache()
        cache.set("k", "v", ttl=60.0)
        remaining = cache.ttl("k")
        assert remaining is not None
        assert 0.0 < remaining <= 60.0

    def test_entry_expires_after_ttl(self) -> None:
        """Validate entry expires after ttl."""
        cache = LocMemCache()
        cache.set("k", "v", ttl=0.05)  # 50 ms
        assert cache.get("k") == "v"
        time.sleep(0.1)
        assert cache.get("k") is None

    def test_ttl_returns_zero_after_expiry(self) -> None:
        """Validate ttl returns zero after expiry."""
        cache = LocMemCache()
        cache.set("k", "v", ttl=0.05)
        time.sleep(0.1)
        # Entry is expired but not yet evicted (get hasn't been called).
        remaining = cache.ttl("k")
        assert remaining == 0.0

    def test_stats_returns_currsize_and_maxsize(self) -> None:
        """Validate stats returns currsize and maxsize."""
        cache = LocMemCache()
        cache.set("a", 1)
        cache.set("b", 2)
        s = cache.stats()
        assert s["maxsize"] is None
        assert s["currsize"] == 2

    def test_stats_excludes_expired_from_currsize(self) -> None:
        """Validate stats excludes expired from currsize."""
        cache = LocMemCache()
        cache.set("live", "v")
        cache.set("dead", "v", ttl=0.05)
        time.sleep(0.1)
        s = cache.stats()
        assert s["currsize"] == 1  # only "live"

    def test_purge_expired_removes_expired_entries(self) -> None:
        """Validate purge expired removes expired entries."""
        cache = LocMemCache()
        cache.set("live", "v")
        cache.set("dead", "v", ttl=0.05)
        time.sleep(0.1)
        removed = cache.purge_expired()
        assert removed == 1
        assert cache.currsize == 1
        assert cache.get("live") == "v"

    def test_purge_expired_returns_zero_when_nothing_expired(self) -> None:
        """Validate purge expired returns zero when nothing expired."""
        cache = LocMemCache()
        cache.set("k", "v", ttl=60.0)
        assert cache.purge_expired() == 0


class TestLocMemCacheConfig:
    """Tests for LocMemCacheConfig (ADR-0010)."""

    def test_is_instance_of_cache_config_base(self) -> None:
        """Validate is instance of cache config base."""
        assert isinstance(LocMemCacheConfig(), CacheConfigBase)

    def test_default_max_size(self) -> None:
        """Validate default max size."""
        config = LocMemCacheConfig()
        assert config.max_size == 1000

    def test_custom_max_size(self) -> None:
        """Validate custom max size."""
        config = LocMemCacheConfig(max_size=500)
        assert config.max_size == 500

    def test_equality(self) -> None:
        """Validate equality."""
        assert LocMemCacheConfig(max_size=100) == LocMemCacheConfig(max_size=100)
        assert LocMemCacheConfig(max_size=100) != LocMemCacheConfig(max_size=200)
