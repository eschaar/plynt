"""Tests for ``plynt.adapters.django.cache``."""

from __future__ import annotations

from types import ModuleType

import pytest

from plynt.adapters.django.cache import DjangoCacheBackend
from plynt.base.cache import CacheBackend
from plynt.base.request import Request
from plynt.base.response import Response


class FakeCache:
    """Minimal Django-like cache backend for unit tests."""

    def __init__(self) -> None:
        self.store: dict[str, object] = {}
        self.last_timeout: int | None = None

    def get(self, key: str, default: object = None) -> object:
        """Return one value by key."""
        return self.store.get(key, default)

    def set(self, key: str, value: object, timeout: int | None = None) -> None:
        """Store one value and record timeout for assertions."""
        self.store[key] = value
        self.last_timeout = timeout

    def delete(self, key: str) -> None:
        """Delete one value by key."""
        self.store.pop(key, None)

    def clear(self) -> None:
        """Clear all values."""
        self.store.clear()


class _FakeDjangoCaches:
    """Cache registry helper that can raise custom alias lookup errors."""

    def __getitem__(self, key: str) -> object:
        del key
        raise _FakeInvalidCacheBackendError("bad cache backend")


class _FakeInvalidCacheBackendError(Exception):
    """Stand-in for Django's InvalidCacheBackendError."""


class TestDjangoCacheBackend:
    """Verify class-level behavior of ``DjangoCacheBackend``."""

    def test_raises_import_error_when_django_is_missing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Raise ``ImportError`` when Django cannot be imported.

        Args:
            monkeypatch: Fixture used to replace ``importlib.import_module``.

        """

        def _raise_import_error(module_name: str) -> ModuleType:
            del module_name
            raise ImportError("django not installed")

        monkeypatch.setattr(
            "plynt.adapters.django.cache.importlib.import_module",
            _raise_import_error,
        )

        with pytest.raises(ImportError, match="Django is required"):
            DjangoCacheBackend()

    def test_raises_key_error_when_alias_is_unknown(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Raise ``KeyError`` for unknown Django cache aliases.

        Args:
            monkeypatch: Fixture used to inject fake django cache module.

        """
        cache_module = ModuleType("django.core.cache")
        cache_module.__dict__["caches"] = {}

        monkeypatch.setattr(
            "plynt.adapters.django.cache.importlib.import_module",
            lambda _: cache_module,
        )

        with pytest.raises(KeyError, match="Unknown Django cache alias"):
            DjangoCacheBackend(alias="missing")

    def test_raises_key_error_for_invalid_cache_backend_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Map Django invalid-backend alias errors to a stable ``KeyError``.

        Args:
            monkeypatch: Fixture used to inject fake django cache module.

        """
        cache_module = ModuleType("django.core.cache")
        cache_module.__dict__["caches"] = _FakeDjangoCaches()
        cache_module.__dict__["InvalidCacheBackendError"] = (
            _FakeInvalidCacheBackendError
        )

        monkeypatch.setattr(
            "plynt.adapters.django.cache.importlib.import_module",
            lambda _: cache_module,
        )

        with pytest.raises(KeyError, match="Unknown Django cache alias"):
            DjangoCacheBackend(alias="broken")

    def test_get_returns_default_for_missing_key(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Return provided default value on cache miss.

        Args:
            monkeypatch: Fixture used to inject fake django cache module.

        """
        backend = _build_backend(monkeypatch)

        assert backend.get("missing", default="fallback") == "fallback"

    def test_set_and_get_roundtrip_response(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Serialize and deserialize ``Response`` values losslessly.

        Args:
            monkeypatch: Fixture used to inject fake django cache module.

        """
        backend = _build_backend(monkeypatch)
        value = Response(
            status_code=201,
            headers={"x-test": "yes"},
            content=b"payload",
        )

        backend.set("k", value, ttl=5.2)
        cached = backend.get("k")

        assert isinstance(cached, Response)
        assert cached.status_code == 201
        assert cached.headers == {"x-test": "yes"}
        assert cached.content == b"payload"

    def test_get_returns_default_for_corrupt_response_payload(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Return default when serialized response payload is invalid.

        Args:
            monkeypatch: Fixture used to inject fake django cache module.

        """
        backend, fake_cache = _build_backend_with_cache(monkeypatch)
        fake_cache.store["broken"] = {
            "schema_version": 1,
            "kind": "plynt.response",
            "status_code": 200,
            "headers": {},
            "content_b64": "not-base64",
        }

        assert backend.get("broken", default="fallback") == "fallback"

    def test_get_returns_default_for_wrong_response_schema(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Return default when response payload schema version is unsupported.

        Args:
            monkeypatch: Fixture used to inject fake django cache module.

        """
        backend, fake_cache = _build_backend_with_cache(monkeypatch)
        fake_cache.store["broken"] = {
            "schema_version": 99,
            "kind": "plynt.response",
            "status_code": 200,
            "headers": {},
            "content_b64": "cGF5bG9hZA==",
        }

        assert backend.get("broken", default="fallback") == "fallback"

    def test_get_returns_default_for_invalid_status_code_type(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Return default when serialized ``status_code`` is not an integer.

        Args:
            monkeypatch: Fixture used to inject fake django cache module.

        """
        backend, fake_cache = _build_backend_with_cache(monkeypatch)
        fake_cache.store["broken"] = {
            "schema_version": 1,
            "kind": "plynt.response",
            "status_code": "200",
            "headers": {},
            "content_b64": "cGF5bG9hZA==",
        }

        assert backend.get("broken", default="fallback") == "fallback"

    def test_get_returns_default_for_invalid_headers_type(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Return default when serialized headers are not mapping-shaped.

        Args:
            monkeypatch: Fixture used to inject fake django cache module.

        """
        backend, fake_cache = _build_backend_with_cache(monkeypatch)
        fake_cache.store["broken"] = {
            "schema_version": 1,
            "kind": "plynt.response",
            "status_code": 200,
            "headers": ["bad"],
            "content_b64": "cGF5bG9hZA==",
        }

        assert backend.get("broken", default="fallback") == "fallback"

    def test_get_returns_default_for_invalid_content_b64_type(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Return default when serialized content is not a base64 string.

        Args:
            monkeypatch: Fixture used to inject fake django cache module.

        """
        backend, fake_cache = _build_backend_with_cache(monkeypatch)
        fake_cache.store["broken"] = {
            "schema_version": 1,
            "kind": "plynt.response",
            "status_code": 200,
            "headers": {},
            "content_b64": 123,
        }

        assert backend.get("broken", default="fallback") == "fallback"

    def test_get_returns_default_for_non_string_header_entries(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Return default when serialized header keys or values are non-strings.

        Args:
            monkeypatch: Fixture used to inject fake django cache module.

        """
        backend, fake_cache = _build_backend_with_cache(monkeypatch)
        fake_cache.store["broken"] = {
            "schema_version": 1,
            "kind": "plynt.response",
            "status_code": 200,
            "headers": {"x": 1},
            "content_b64": "cGF5bG9hZA==",
        }

        assert backend.get("broken", default="fallback") == "fallback"

    def test_get_returns_non_response_values_as_is(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Return non-``Response`` payloads without transformation.

        Args:
            monkeypatch: Fixture used to inject fake django cache module.

        """
        backend, fake_cache = _build_backend_with_cache(monkeypatch)
        fake_cache.store["token"] = {"access_token": "abc"}

        assert backend.get("token") == {"access_token": "abc"}

    def test_set_uses_none_timeout_for_none_ttl(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Pass ``None`` timeout through when no TTL is given.

        Args:
            monkeypatch: Fixture used to inject fake django cache module.

        """
        backend, fake_cache = _build_backend_with_cache(monkeypatch)

        backend.set("k", "v", ttl=None)

        assert fake_cache.last_timeout is None

    def test_set_rounds_ttl_up_to_integer_timeout(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Round TTL values up for Django timeout compatibility.

        Args:
            monkeypatch: Fixture used to inject fake django cache module.

        """
        backend, fake_cache = _build_backend_with_cache(monkeypatch)

        backend.set("k", "v", ttl=1.2)

        assert fake_cache.last_timeout == 2

    def test_set_maps_negative_ttl_to_zero(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Clamp negative TTL values to ``0`` for immediate expiry.

        Args:
            monkeypatch: Fixture used to inject fake django cache module.

        """
        backend, fake_cache = _build_backend_with_cache(monkeypatch)

        backend.set("k", "v", ttl=-4)

        assert fake_cache.last_timeout == 0

    def test_delete_delegates_to_django_cache(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Delete one key through the underlying Django cache backend.

        Args:
            monkeypatch: Fixture used to inject fake django cache module.

        """
        backend, fake_cache = _build_backend_with_cache(monkeypatch)
        fake_cache.store["k"] = "v"

        backend.delete("k")

        assert "k" not in fake_cache.store

    def test_clear_delegates_to_django_cache(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Clear all keys through the underlying Django cache backend.

        Args:
            monkeypatch: Fixture used to inject fake django cache module.

        """
        backend, fake_cache = _build_backend_with_cache(monkeypatch)
        fake_cache.store["a"] = "1"
        fake_cache.store["b"] = "2"

        backend.clear()

        assert fake_cache.store == {}

    def test_cache_key_matches_core_cache_backend(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Use the shared core cache key algorithm for request hashing.

        Args:
            monkeypatch: Fixture used to inject fake django cache module.

        """
        backend = _build_backend(monkeypatch)
        request = Request(method="GET", url="https://api.example.com/items")

        assert backend.cache_key(request) == CacheBackend.cache_key(request)

    def test_roundtrip_response_with_real_django_locmem_backend(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Roundtrip a response using Django's real ``LocMemCache`` backend.

        Args:
            monkeypatch: Fixture used to inject cache module lookup.

        """
        django_cache_backend = pytest.importorskip("django.core.cache.backends.locmem")
        locmem_cache = django_cache_backend.LocMemCache(
            "plynt-test-locmem",
            {},
        )
        cache_module = ModuleType("django.core.cache")
        cache_module.__dict__["caches"] = {"default": locmem_cache}

        monkeypatch.setattr(
            "plynt.adapters.django.cache.importlib.import_module",
            lambda _: cache_module,
        )

        backend = DjangoCacheBackend(alias="default")
        value = Response(
            status_code=200,
            headers={"content-type": "application/json"},
            content=b'{"ok":true}',
        )

        backend.set("real-locmem", value, ttl=10)
        cached = backend.get("real-locmem")

        assert isinstance(cached, Response)
        assert cached.status_code == value.status_code
        assert cached.headers == value.headers
        assert cached.content == value.content


def _build_backend(monkeypatch: pytest.MonkeyPatch) -> DjangoCacheBackend:
    """Build a backend with one fake default cache alias.

    Args:
        monkeypatch: Fixture used to inject fake django cache module.

    Returns:
        A configured ``DjangoCacheBackend`` instance.

    """
    backend, _ = _build_backend_with_cache(monkeypatch)
    return backend


def _build_backend_with_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[DjangoCacheBackend, FakeCache]:
    """Build a backend and return it with its fake cache object.

    Args:
        monkeypatch: Fixture used to inject fake django cache module.

    Returns:
        Tuple of configured backend and fake cache storage object.

    """
    fake_cache = FakeCache()
    cache_module = ModuleType("django.core.cache")
    cache_module.__dict__["caches"] = {"default": fake_cache}

    monkeypatch.setattr(
        "plynt.adapters.django.cache.importlib.import_module",
        lambda _: cache_module,
    )

    return DjangoCacheBackend(alias="default"), fake_cache
