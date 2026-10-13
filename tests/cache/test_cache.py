"""Tests for plynth.cache (CacheConfigBase protocol and cache_from_config factory)."""

from __future__ import annotations

import sys
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from plynth.base.cache import (
    CacheBackend,
    CacheConfigBase,
    SupportsSizeInfo,
    SupportsStats,
    SupportsTTL,
)
from plynth.cache import (
    DummyCache,
    DummyCacheConfig,
    LocMemCache,
    LocMemCacheConfig,
    RedisCache,
    RedisCacheConfig,
    cache_from_config,
)


class TestIncompleteCacheBackend:
    """Ensure inherited contract methods fail instead of silently succeeding"""

    @pytest.mark.parametrize(
        ("method", "arguments"),
        [
            ("get", ("key",)),
            ("set", ("key", "value")),
            ("delete", ("key",)),
            ("clear", ()),
            ("ttl", ("key",)),
            ("stats", ()),
        ],
    )
    def test_unimplemented_operation_raises(
        self, method: str, arguments: tuple[str, ...]
    ) -> None:
        backend = self._incomplete_backend()

        with pytest.raises(NotImplementedError):
            getattr(backend, method)(*arguments)

    @pytest.mark.parametrize("attribute", ["maxsize", "currsize"])
    def test_unimplemented_size_property_raises(self, attribute: str) -> None:
        backend = self._incomplete_backend()

        with pytest.raises(NotImplementedError):
            getattr(backend, attribute)

    @staticmethod
    def _incomplete_backend() -> Any:
        class IncompleteBackend(
            CacheBackend, SupportsTTL, SupportsStats, SupportsSizeInfo
        ):
            pass

        backend_type: type[Any] = IncompleteBackend
        return backend_type()


class TestCacheConfigBase:
    """Tests for CacheConfigBase marker class."""

    def test_all_configs_are_instances_of_base(self) -> None:
        """Validate all configs are instances of base."""
        assert isinstance(DummyCacheConfig(), CacheConfigBase)
        assert isinstance(LocMemCacheConfig(), CacheConfigBase)
        assert isinstance(
            RedisCacheConfig(location="redis://localhost:6379/0"), CacheConfigBase
        )

    def test_unrelated_object_is_not_an_instance(self) -> None:
        """Validate unrelated object is not an instance."""
        assert not isinstance("redis://localhost", CacheConfigBase)
        assert not isinstance(42, CacheConfigBase)
        assert not isinstance(DummyCache(), CacheConfigBase)


class TestCacheFromConfig:
    """Tests for the cache_from_config() typed factory (ADR-0010)."""

    def test_dummy_config_returns_dummy_cache(self) -> None:
        """Validate dummy config returns dummy cache."""
        backend = cache_from_config(DummyCacheConfig())
        assert isinstance(backend, DummyCache)

    def test_dummy_cache_is_noop(self) -> None:
        """Validate dummy cache is noop."""
        backend = cache_from_config(DummyCacheConfig())
        backend.set("k", "v")
        assert backend.get("k") is None

    def test_locmem_config_returns_locmem_cache(self) -> None:
        """Validate locmem config returns locmem cache."""
        backend = cache_from_config(LocMemCacheConfig())
        assert isinstance(backend, LocMemCache)

    def test_locmem_cache_is_functional(self) -> None:
        """Validate locmem cache is functional."""
        backend = cache_from_config(LocMemCacheConfig())
        backend.set("key", "value")
        assert backend.get("key") == "value"

    def test_redis_raises_import_error_without_package(self) -> None:
        """Validate redis raises import error without package."""
        config = RedisCacheConfig(location="redis://localhost:6379/0")
        with patch.dict(sys.modules, {"redis": None}):
            with pytest.raises(ImportError, match="redis"):
                cache_from_config(config)

    def test_redis_config_returns_redis_backend_adapter(self) -> None:
        """Validate redis config returns redis backend adapter."""
        mock_client = MagicMock()
        mock_redis_module = MagicMock()
        mock_redis_module.from_url.return_value = mock_client
        config = RedisCacheConfig(
            location="redis://localhost:6379/0", key_prefix="app:"
        )
        with patch.dict(sys.modules, {"redis": mock_redis_module}):
            backend = cache_from_config(config)
        assert isinstance(backend, RedisCache)
        mock_redis_module.from_url.assert_called_once_with("redis://localhost:6379/0")

    def test_redis_config_passes_socket_timeout(self) -> None:
        """Validate redis config passes socket timeout."""
        mock_client = MagicMock()
        mock_redis_module = MagicMock()
        mock_redis_module.from_url.return_value = mock_client
        config = RedisCacheConfig(
            location="redis://localhost:6379/0", socket_timeout=2.0
        )
        with patch.dict(sys.modules, {"redis": mock_redis_module}):
            cache_from_config(config)
        _, kwargs = mock_redis_module.from_url.call_args
        assert kwargs.get("socket_timeout") == 2.0

    def test_redis_config_passes_max_connections(self) -> None:
        """Validate redis config passes max connections."""
        mock_client = MagicMock()
        mock_redis_module = MagicMock()
        mock_redis_module.from_url.return_value = mock_client
        config = RedisCacheConfig(
            location="redis://localhost:6379/0", max_connections=20
        )
        with patch.dict(sys.modules, {"redis": mock_redis_module}):
            cache_from_config(config)
        _, kwargs = mock_redis_module.from_url.call_args
        assert kwargs.get("max_connections") == 20

    def test_redis_config_passes_retry_on_timeout(self) -> None:
        """Validate redis config passes retry on timeout."""
        mock_client = MagicMock()
        mock_redis_module = MagicMock()
        mock_redis_module.from_url.return_value = mock_client
        config = RedisCacheConfig(
            location="redis://localhost:6379/0", retry_on_timeout=True
        )
        with patch.dict(sys.modules, {"redis": mock_redis_module}):
            cache_from_config(config)
        _, kwargs = mock_redis_module.from_url.call_args
        assert kwargs.get("retry_on_timeout") is True

    def test_redis_config_omits_none_options(self) -> None:
        """Options that are None must not be passed to redis.from_url."""
        mock_client = MagicMock()
        mock_redis_module = MagicMock()
        mock_redis_module.from_url.return_value = mock_client
        config = RedisCacheConfig(location="redis://localhost:6379/0")
        with patch.dict(sys.modules, {"redis": mock_redis_module}):
            cache_from_config(config)
        _, kwargs = mock_redis_module.from_url.call_args
        assert "socket_timeout" not in kwargs
        assert "max_connections" not in kwargs
        assert "ssl_certfile" not in kwargs
        assert "ssl_keyfile" not in kwargs
        assert "ssl_ca_certs" not in kwargs

    def test_redis_config_uses_key_prefix(self) -> None:
        """Validate redis config uses key prefix."""
        mock_client = MagicMock()
        mock_redis_module = MagicMock()
        mock_redis_module.from_url.return_value = mock_client
        config = RedisCacheConfig(
            location="redis://localhost:6379/0", key_prefix="myapp:"
        )
        with patch.dict(sys.modules, {"redis": mock_redis_module}):
            backend = cache_from_config(config)
        assert isinstance(backend, RedisCache)
        assert backend._prefix == "myapp:"

    def test_redis_config_passes_ssl_options(self) -> None:
        """Validate redis config passes ssl options."""
        mock_client = MagicMock()
        mock_redis_module = MagicMock()
        mock_redis_module.from_url.return_value = mock_client
        config = RedisCacheConfig(
            location="rediss://myhost:6380/0",
            ssl_certfile="/etc/ssl/client.crt",
            ssl_keyfile="/etc/ssl/client.key",
            ssl_ca_certs="/etc/ssl/ca.crt",
        )
        with patch.dict(sys.modules, {"redis": mock_redis_module}):
            cache_from_config(config)
        _, kwargs = mock_redis_module.from_url.call_args
        assert kwargs.get("ssl_certfile") == "/etc/ssl/client.crt"
        assert kwargs.get("ssl_keyfile") == "/etc/ssl/client.key"
        assert kwargs.get("ssl_ca_certs") == "/etc/ssl/ca.crt"
