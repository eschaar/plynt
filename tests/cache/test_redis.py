"""Tests for plynth.cache.redis (RedisCache, RedisCacheConfig)."""

from __future__ import annotations

import pickle
from unittest.mock import patch

import fakeredis
import pytest

from plynth.base.cache import (
    CacheBackend,
    CacheConfigBase,
    SupportsStats,
    SupportsTTL,
)
from plynth.cache import RedisCache, RedisCacheConfig


class TestRedisCache:
    """Test suite for RedisCache."""

    def _make(self, prefix: str = "test:") -> RedisCache:
        """Handle make."""
        return RedisCache(fakeredis.FakeRedis(host="127.0.0.1"), prefix=prefix)

    def test_satisfies_cache_backend_protocol(self) -> None:
        """Validate satisfies cache backend protocol."""
        assert isinstance(self._make(), CacheBackend)

    def test_satisfies_supports_ttl_protocol(self) -> None:
        """Validate satisfies supports ttl protocol."""
        assert isinstance(self._make(), SupportsTTL)

    def test_satisfies_supports_stats_protocol(self) -> None:
        """Validate satisfies supports stats protocol."""
        assert isinstance(self._make(), SupportsStats)

    def test_set_and_get_roundtrip(self) -> None:
        """Validate set and get roundtrip."""
        backend = self._make()
        backend.set("k", {"data": 42})
        assert backend.get("k") == {"data": 42}

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

    def test_clear_removes_only_prefixed_keys(self) -> None:
        """Validate clear removes only prefixed keys."""
        fake = fakeredis.FakeRedis(host="127.0.0.1")
        backend = RedisCache(fake, prefix="plynth:")
        backend.set("a", 1)
        backend.set("b", 2)
        # Store a key outside our prefix directly via the Redis client.
        fake.set("other:key", pickle.dumps("should stay"))
        backend.clear()
        assert backend.get("a") is None
        assert backend.get("b") is None
        # Key outside prefix must be untouched.
        assert fake.get("other:key") is not None

    def test_set_with_ttl_stores_expiring_entry(self) -> None:
        """Validate set with ttl stores expiring entry."""
        backend = self._make()
        backend.set("k", "v", ttl=60.0)
        assert backend.get("k") == "v"

    def test_ttl_returns_remaining_seconds(self) -> None:
        """Validate ttl returns remaining seconds."""
        backend = self._make()
        backend.set("k", "v", ttl=30.0)
        remaining = backend.ttl("k")
        assert remaining is not None
        assert 0.0 < remaining <= 30.0

    def test_ttl_none_when_no_expiry(self) -> None:
        """Validate ttl none when no expiry."""
        backend = self._make()
        backend.set("k", "v")  # no ttl
        assert backend.ttl("k") is None

    def test_ttl_zero_for_absent_key(self) -> None:
        """Validate ttl zero for absent key."""
        backend = self._make()
        assert backend.ttl("absent") == 0.0

    def test_stats_returns_expected_keys(self) -> None:
        """Validate stats returns expected keys."""
        backend = self._make()
        # fakeredis does not implement INFO; mock it to test key mapping only.
        with patch.object(
            backend._client,
            "info",
            return_value={
                "connected_clients": 1,
                "used_memory_human": "1.00M",
                "keyspace_hits": 0,
                "keyspace_misses": 0,
            },
        ):
            s = backend.stats()
        assert "connected_clients" in s
        assert "used_memory_human" in s
        assert "keyspace_hits" in s
        assert "keyspace_misses" in s


class TestRedisCacheConfig:
    """Tests for RedisCacheConfig (ADR-0010)."""

    def test_is_instance_of_cache_config_base(self) -> None:
        """Validate is instance of cache config base."""
        assert isinstance(
            RedisCacheConfig(location="redis://localhost:6379/0"), CacheConfigBase
        )

    def test_requires_location(self) -> None:
        """Validate requires location."""
        with pytest.raises(TypeError):
            RedisCacheConfig(**{})

    def test_empty_location_raises(self) -> None:
        """Validate empty location raises."""
        with pytest.raises(ValueError, match="non-empty location"):
            RedisCacheConfig(location="")

    def test_invalid_scheme_raises(self) -> None:
        """Validate invalid scheme raises."""
        with pytest.raises(ValueError, match="redis:// or rediss://"):
            RedisCacheConfig(location="locmem://default")

    def test_http_scheme_raises(self) -> None:
        """Validate http scheme raises."""
        with pytest.raises(ValueError, match="redis://"):
            RedisCacheConfig(location="http://localhost:6379/0")

    def test_valid_redis_url(self) -> None:
        """Validate valid redis url."""
        config = RedisCacheConfig(location="redis://localhost:6379/0")
        assert config.location == "redis://localhost:6379/0"

    def test_valid_rediss_url(self) -> None:
        """Validate valid rediss url."""
        config = RedisCacheConfig(location="rediss://myhost:6380/1")
        assert config.location == "rediss://myhost:6380/1"

    def test_default_key_prefix(self) -> None:
        """Validate default key prefix."""
        config = RedisCacheConfig(location="redis://localhost:6379/0")
        assert config.key_prefix == "plynth:"

    def test_custom_key_prefix(self) -> None:
        """Validate custom key prefix."""
        config = RedisCacheConfig(
            location="redis://localhost:6379/0", key_prefix="app:"
        )
        assert config.key_prefix == "app:"

    def test_socket_timeout_default_is_none(self) -> None:
        """Validate socket timeout default is none."""
        config = RedisCacheConfig(location="redis://localhost:6379/0")
        assert config.socket_timeout is None

    def test_custom_socket_timeout(self) -> None:
        """Validate custom socket timeout."""
        config = RedisCacheConfig(
            location="redis://localhost:6379/0", socket_timeout=2.5
        )
        assert config.socket_timeout == 2.5

    def test_retry_on_timeout_default_false(self) -> None:
        """Validate retry on timeout default false."""
        config = RedisCacheConfig(location="redis://localhost:6379/0")
        assert config.retry_on_timeout is False

    def test_max_connections_default_is_none(self) -> None:
        """Validate max connections default is none."""
        config = RedisCacheConfig(location="redis://localhost:6379/0")
        assert config.max_connections is None

    def test_ssl_fields_default_to_none(self) -> None:
        """Validate ssl fields default to none."""
        config = RedisCacheConfig(location="redis://localhost:6379/0")
        assert config.ssl_certfile is None
        assert config.ssl_keyfile is None
        assert config.ssl_ca_certs is None

    def test_all_options(self) -> None:
        """Validate all options."""
        config = RedisCacheConfig(
            location="rediss://myhost:6380/0",
            key_prefix="svc:",
            socket_timeout=1.0,
            retry_on_timeout=True,
            max_connections=10,
            ssl_certfile="/etc/ssl/client.crt",
            ssl_keyfile="/etc/ssl/client.key",
            ssl_ca_certs="/etc/ssl/ca.crt",
        )
        assert config.socket_timeout == 1.0
        assert config.retry_on_timeout is True
        assert config.max_connections == 10
        assert config.ssl_certfile == "/etc/ssl/client.crt"
        assert config.ssl_keyfile == "/etc/ssl/client.key"
        assert config.ssl_ca_certs == "/etc/ssl/ca.crt"
