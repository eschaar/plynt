"""Tests for plynth.base.cache and plynth.middleware.cache.

Cache protocol, CacheMiddleware, CacheBackend._cache_key.

Cache middleware tests verify the full chain-of-responsibility contract:
short-circuiting on a GET cache hit, delegating on a miss, storing successful
GET responses, and leaving non-GET or error responses uncached.
"""

from __future__ import annotations

from typing import Any

import pytest

from plynth.base.cache import (
    CacheBackend,
    SupportsSizeInfo,
    SupportsStats,
    SupportsTTL,
)
from plynth.base.middleware import AsyncMiddleware, SyncMiddleware
from plynth.base.request import Request
from plynth.base.response import Response
from plynth.middleware.cache import (
    AsyncCacheMiddleware,
    CacheMiddleware,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _req(
    method: str = "GET",
    url: str = "https://example.com/items",
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> Request:
    """Handle req."""
    return Request(
        method=method,
        url=url,
        params=params or {},
        headers=headers or {},
    )


def _resp(status: int = 200) -> Response:
    """Handle resp."""
    return Response(status_code=status)


class _RecordingCache(CacheBackend):
    """CacheBackend that records all calls and stores values in memory."""

    def __init__(self, prefill: dict[str, Any] | None = None) -> None:
        """Initialize _RecordingCache."""
        self._store: dict[str, Any] = dict(prefill or {})
        self.get_calls: list[str] = []
        self.set_calls: list[tuple[str, Any]] = []
        self.delete_calls: list[str] = []
        self.clear_calls: int = 0

    def get(self, key: str, default: Any = None) -> Any:
        """Return get."""
        self.get_calls.append(key)
        return self._store.get(key, default)

    def set(self, key: str, value: Any, ttl: float | None = None) -> None:
        """Return set."""
        self.set_calls.append((key, value))
        self._store[key] = value

    def delete(self, key: str) -> None:
        """Return delete."""
        self.delete_calls.append(key)
        self._store.pop(key, None)

    def clear(self) -> None:
        """Return clear."""
        self.clear_calls += 1
        self._store.clear()


class _CountingNextHandler:
    """Sync next_handler that counts invocations and returns a fixed response."""

    def __init__(self, response: Response) -> None:
        """Initialize _CountingNextHandler."""
        self._response = response
        self.calls: int = 0

    def __call__(self, request: Request) -> Response:
        """Handle call."""
        self.calls += 1
        return self._response


class _AsyncCountingNextHandler:
    """Async next_handler that counts invocations and returns a fixed response."""

    def __init__(self, response: Response) -> None:
        """Initialize _AsyncCountingNextHandler."""
        self._response = response
        self.calls: int = 0

    async def __call__(self, request: Request) -> Response:
        """Handle call."""
        self.calls += 1
        return self._response


# ---------------------------------------------------------------------------
# CacheBackend protocol
# ---------------------------------------------------------------------------


class TestCacheBackendProtocol:
    """Test suite for CacheBackendProtocol."""

    def test_complete_class_satisfies_protocol(self) -> None:
        """Validate complete class satisfies protocol."""
        assert isinstance(_RecordingCache(), CacheBackend)

    def test_missing_get_does_not_satisfy(self) -> None:
        """Validate missing get does not satisfy."""

        class PartialCache:
            """Represent PartialCache."""

            def set(self, key: str, value: Any, ttl: float | None = None) -> None:
                """Return set."""

            def delete(self, key: str) -> None:
                """Return delete."""

            def clear(self) -> None:
                """Return clear."""

        assert not isinstance(PartialCache(), CacheBackend)

    def test_missing_set_does_not_satisfy(self) -> None:
        """Validate missing set does not satisfy."""

        class PartialCache:
            """Represent PartialCache."""

            def get(self, key: str, default: Any = None) -> Any:
                """Return get."""
                return default

            def delete(self, key: str) -> None:
                """Return delete."""

            def clear(self) -> None:
                """Return clear."""

        assert not isinstance(PartialCache(), CacheBackend)

    def test_missing_delete_does_not_satisfy(self) -> None:
        """Validate missing delete does not satisfy."""

        class PartialCache:
            """Represent PartialCache."""

            def get(self, key: str, default: Any = None) -> Any:
                """Return get."""
                return default

            def set(self, key: str, value: Any, ttl: float | None = None) -> None:
                """Return set."""

            def clear(self) -> None:
                """Return clear."""

        assert not isinstance(PartialCache(), CacheBackend)

    def test_missing_clear_does_not_satisfy(self) -> None:
        """Validate missing clear does not satisfy."""

        class PartialCache:
            """Represent PartialCache."""

            def get(self, key: str, default: Any = None) -> Any:
                """Return get."""
                return default

            def set(self, key: str, value: Any, ttl: float | None = None) -> None:
                """Return set."""

            def delete(self, key: str) -> None:
                """Return delete."""

        assert not isinstance(PartialCache(), CacheBackend)

    def test_get_returns_default_for_missing_key(self) -> None:
        """Validate get returns default for missing key."""
        cache = _RecordingCache()
        assert cache.get("missing") is None
        assert cache.get("missing", "fallback") == "fallback"

    def test_set_and_get_roundtrip(self) -> None:
        """Validate set and get roundtrip."""
        cache = _RecordingCache()
        resp = _resp(200)
        cache.set("key1", resp)
        assert cache.get("key1") is resp

    def test_delete_removes_entry(self) -> None:
        """Validate delete removes entry."""
        cache = _RecordingCache()
        cache.set("key1", _resp(200))
        cache.delete("key1")
        assert cache.get("key1") is None

    def test_delete_missing_key_is_noop(self) -> None:
        """Validate delete missing key is noop."""
        cache = _RecordingCache()
        cache.delete("nonexistent")  # must not raise

    def test_clear_removes_all_entries(self) -> None:
        """Validate clear removes all entries."""
        cache = _RecordingCache()
        cache.set("a", _resp(200))
        cache.set("b", _resp(201))
        cache.clear()
        assert cache.get("a") is None
        assert cache.get("b") is None

    def test_overwrite_existing_key(self) -> None:
        """Validate overwrite existing key."""
        cache = _RecordingCache()
        r1 = Response(status_code=200, content=b"first")
        r2 = Response(status_code=200, content=b"second")
        cache.set("k", r1)
        cache.set("k", r2)
        assert cache.get("k") is r2

    def test_returns_64_char_hex_digest(self) -> None:
        """Validate returns 64 char hex digest."""
        key = CacheBackend.cache_key(_req(url="https://example.com/items"))
        assert len(key) == 64
        assert all(c in "0123456789abcdef" for c in key)

    def test_same_url_produces_same_key(self) -> None:
        """Validate same url produces same key."""
        req = _req(url="https://example.com/items")
        key1 = CacheBackend.cache_key(req)
        key2 = CacheBackend.cache_key(req)
        assert key1 == key2

    def test_different_urls_produce_different_keys(self) -> None:
        """Validate different urls produce different keys."""
        key1 = CacheBackend.cache_key(_req(url="https://example.com/a"))
        key2 = CacheBackend.cache_key(_req(url="https://example.com/b"))
        assert key1 != key2

    def test_params_change_the_key(self) -> None:
        """Validate params change the key."""
        key_bare = CacheBackend.cache_key(_req(params=None))
        key_with = CacheBackend.cache_key(_req(params={"q": "hello"}))
        assert key_bare != key_with

    def test_empty_params_produces_same_key_as_no_params(self) -> None:
        """Validate empty params produces same key as no params."""
        assert CacheBackend.cache_key(_req(params=None)) == CacheBackend.cache_key(
            _req(params={})
        )

    def test_same_params_different_order_produce_same_key(self) -> None:
        """Validate same params different order produce same key."""
        req1 = _req(params={"a": "1", "b": "2"})
        req2 = _req(params={"b": "2", "a": "1"})
        assert CacheBackend.cache_key(req1) == CacheBackend.cache_key(req2)

    def test_different_param_values_produce_different_keys(self) -> None:
        """Validate different param values produce different keys."""
        key1 = CacheBackend.cache_key(_req(params={"q": "foo"}))
        key2 = CacheBackend.cache_key(_req(params={"q": "bar"}))
        assert key1 != key2

    def test_method_changes_the_key(self) -> None:
        """Validate request method contributes to cache key partitioning."""
        key_get = CacheBackend.cache_key(_req(method="GET"))
        key_post = CacheBackend.cache_key(_req(method="POST"))
        assert key_get != key_post

    def test_authorization_header_changes_the_key(self) -> None:
        """Validate authorization header contributes to cache key partitioning."""
        key_a = CacheBackend.cache_key(
            _req(headers={"Authorization": "Bearer token-a"})
        )
        key_b = CacheBackend.cache_key(
            _req(headers={"Authorization": "Bearer token-b"})
        )
        assert key_a != key_b

    def test_header_name_case_does_not_change_the_key(self) -> None:
        """Validate cache key normalizes header-name casing."""
        key_a = CacheBackend.cache_key(
            _req(headers={"Authorization": "Bearer token-a"})
        )
        key_b = CacheBackend.cache_key(
            _req(headers={"authorization": "Bearer token-a"})
        )
        assert key_a == key_b


# ---------------------------------------------------------------------------
# Capability protocols
# ---------------------------------------------------------------------------


class TestCapabilityProtocols:
    """Test suite for CapabilityProtocols."""

    def test_supports_ttl_satisfied_by_object_with_ttl_method(self) -> None:
        """Validate supports ttl satisfied by object with ttl method."""

        class WithTTL:
            """Represent WithTTL."""

            def ttl(self, key: str) -> float | None:
                """Return ttl."""
                return None

        assert isinstance(WithTTL(), SupportsTTL)

    def test_supports_ttl_not_satisfied_without_ttl_method(self) -> None:
        """Validate supports ttl not satisfied without ttl method."""

        class WithoutTTL:
            """Represent WithoutTTL."""

        assert not isinstance(WithoutTTL(), SupportsTTL)

    def test_supports_stats_satisfied_by_object_with_stats_method(self) -> None:
        """Validate supports stats satisfied by object with stats method."""

        class WithStats:
            """Represent WithStats."""

            def stats(self) -> dict[str, Any]:
                """Return stats."""
                return {}

        assert isinstance(WithStats(), SupportsStats)

    def test_supports_stats_not_satisfied_without_stats_method(self) -> None:
        """Validate supports stats not satisfied without stats method."""

        class WithoutStats:
            """Represent WithoutStats."""

        assert not isinstance(WithoutStats(), SupportsStats)

    def test_supports_size_info_satisfied_by_object_with_both_attrs(
        self,
    ) -> None:
        """Validate supports size info satisfied by object with both attrs."""

        class WithSize:
            """Represent WithSize."""

            maxsize: int | None = 100
            currsize: int = 0

        assert isinstance(WithSize(), SupportsSizeInfo)

    def test_supports_size_info_not_satisfied_without_maxsize(self) -> None:
        """Validate supports size info not satisfied without maxsize."""

        class WithoutMaxsize:
            """Represent WithoutMaxsize."""

            currsize: int = 0

        assert not isinstance(WithoutMaxsize(), SupportsSizeInfo)

    def test_supports_size_info_not_satisfied_without_currsize(self) -> None:
        """Validate supports size info not satisfied without currsize."""

        class WithoutCurrsize:
            """Represent WithoutCurrsize."""

            maxsize: int | None = None

        assert not isinstance(WithoutCurrsize(), SupportsSizeInfo)


# ---------------------------------------------------------------------------
# CacheMiddleware
# ---------------------------------------------------------------------------


class TestCacheMiddleware:
    """Test suite for CacheMiddleware."""

    def test_satisfies_sync_middleware_protocol(self) -> None:
        """Validate satisfies sync middleware protocol."""
        assert isinstance(CacheMiddleware(_RecordingCache()), SyncMiddleware)

    def test_cache_miss_calls_next_handler(self) -> None:
        """Validate cache miss calls next handler."""
        cache = _RecordingCache()
        mw = CacheMiddleware(cache)
        handler = _CountingNextHandler(_resp(200))
        mw.handle(_req("GET"), handler)
        assert handler.calls == 1

    def test_cache_hit_does_not_call_next_handler(self) -> None:
        """Validate cache hit does not call next handler."""
        cached = _resp(200)
        req = _req("GET")
        cache = _RecordingCache(prefill={CacheBackend.cache_key(req): cached})
        mw = CacheMiddleware(cache)
        handler = _CountingNextHandler(_resp(500))
        result = mw.handle(req, handler)
        assert result.status_code == cached.status_code
        assert result is not cached
        assert handler.calls == 0

    def test_cache_miss_stores_successful_response(self) -> None:
        """Validate cache miss stores successful response."""
        cache = _RecordingCache()
        mw = CacheMiddleware(cache)
        req = _req("GET")
        mw.handle(req, _CountingNextHandler(_resp(200)))
        assert len(cache.set_calls) == 1
        key, stored = cache.set_calls[0]
        assert key == CacheBackend.cache_key(req)
        assert stored.status_code == 200

    def test_error_response_not_stored(self) -> None:
        """Validate error response not stored."""
        cache = _RecordingCache()
        mw = CacheMiddleware(cache)
        for status in (400, 404, 500, 503):
            cache.set_calls.clear()
            mw.handle(_req("GET"), _CountingNextHandler(_resp(status)))
            assert cache.set_calls == [], f"status {status} should not be cached"

    def test_non_get_request_not_cached(self) -> None:
        """Validate non get request not cached."""
        cache = _RecordingCache()
        mw = CacheMiddleware(cache)
        for method in ("POST", "PUT", "PATCH", "DELETE"):
            mw.handle(_req(method), _CountingNextHandler(_resp(200)))
        assert cache.get_calls == []
        assert cache.set_calls == []

    def test_returns_response_from_next_handler(self) -> None:
        """Validate returns response from next handler."""
        expected = _resp(201)
        cache = _RecordingCache()
        mw = CacheMiddleware(cache)
        result = mw.handle(_req("GET"), _CountingNextHandler(expected))
        assert result is expected

    def test_cache_key_includes_params(self) -> None:
        """Validate cache key includes params."""
        cache = _RecordingCache()
        mw = CacheMiddleware(cache)
        req_with_params = _req(params={"q": "hello"})
        req_without_params = _req(params=None)
        mw.handle(req_with_params, _CountingNextHandler(_resp(200)))
        assert len(cache.set_calls) == 1
        key, _ = cache.set_calls[0]
        # Keys for same URL with and without params must differ.
        assert key == CacheBackend.cache_key(req_with_params)
        assert key != CacheBackend.cache_key(req_without_params)

    def test_second_get_hits_cache(self) -> None:
        """Validate second get hits cache."""
        cache = _RecordingCache()
        mw = CacheMiddleware(cache)
        handler = _CountingNextHandler(_resp(200))
        mw.handle(_req("GET"), handler)
        # Second call: cache is populated, next_handler should not be called again.
        result = mw.handle(_req("GET"), handler)
        assert result.status_code == 200
        assert handler.calls == 1

    def test_corrupt_cache_value_raises_type_error(self) -> None:
        """Validate corrupt cache value raises type error."""
        cache = _RecordingCache()
        req = _req("GET")
        cache._store[CacheBackend.cache_key(req)] = "not-a-response"
        mw = CacheMiddleware(cache)
        with pytest.raises(TypeError, match="Cached value must be Response"):
            mw.handle(req, _CountingNextHandler(_resp(200)))

    def test_cached_response_is_defensively_copied_on_read(self) -> None:
        """Validate cache hits return copies so caller mutations do not taint cache."""
        req = _req("GET")
        cached = Response(status_code=200, headers={"X-Test": "v1"}, content=b"ok")
        cache = _RecordingCache(prefill={CacheBackend.cache_key(req): cached})
        mw = CacheMiddleware(cache)

        first = mw.handle(req, _CountingNextHandler(_resp(500)))
        first.headers["X-Test"] = "mutated"

        second = mw.handle(req, _CountingNextHandler(_resp(500)))
        assert second.headers["X-Test"] == "v1"


# ---------------------------------------------------------------------------
# AsyncCacheMiddleware
# ---------------------------------------------------------------------------


class TestAsyncCacheMiddleware:
    """Test suite for AsyncCacheMiddleware."""

    def test_satisfies_async_middleware_protocol(self) -> None:
        """Validate satisfies async middleware protocol."""
        assert isinstance(AsyncCacheMiddleware(_RecordingCache()), AsyncMiddleware)

    async def test_cache_miss_calls_next_handler(self) -> None:
        """Validate cache miss calls next handler."""
        cache = _RecordingCache()
        mw = AsyncCacheMiddleware(cache)
        handler = _AsyncCountingNextHandler(_resp(200))
        await mw.handle(_req("GET"), handler)
        assert handler.calls == 1

    async def test_cache_hit_does_not_call_next_handler(self) -> None:
        """Validate cache hit does not call next handler."""
        cached = _resp(200)
        req = _req("GET")
        cache = _RecordingCache(prefill={CacheBackend.cache_key(req): cached})
        mw = AsyncCacheMiddleware(cache)
        handler = _AsyncCountingNextHandler(_resp(500))
        result = await mw.handle(req, handler)
        assert result.status_code == cached.status_code
        assert result is not cached
        assert handler.calls == 0

    async def test_cache_miss_stores_successful_response(self) -> None:
        """Validate cache miss stores successful response."""
        cache = _RecordingCache()
        mw = AsyncCacheMiddleware(cache)
        handler = _AsyncCountingNextHandler(_resp(200))
        await mw.handle(_req("GET"), handler)
        assert len(cache.set_calls) == 1

    async def test_error_response_not_stored(self) -> None:
        """Validate error response not stored."""
        cache = _RecordingCache()
        mw = AsyncCacheMiddleware(cache)
        for status in (400, 500):
            cache.set_calls.clear()
            handler = _AsyncCountingNextHandler(_resp(status))
            await mw.handle(_req("GET"), handler)
            assert cache.set_calls == []

    async def test_non_get_request_not_cached(self) -> None:
        """Validate non get request not cached."""
        cache = _RecordingCache()
        mw = AsyncCacheMiddleware(cache)
        for method in ("POST", "PUT", "DELETE"):
            handler = _AsyncCountingNextHandler(_resp(200))
            await mw.handle(_req(method), handler)
        assert cache.get_calls == []
        assert cache.set_calls == []

    async def test_returns_response_from_next_handler(self) -> None:
        """Validate returns response from next handler."""
        expected = _resp(201)
        cache = _RecordingCache()
        mw = AsyncCacheMiddleware(cache)
        handler = _AsyncCountingNextHandler(expected)
        result = await mw.handle(_req("GET"), handler)
        assert result is expected

    async def test_corrupt_cache_value_raises_type_error(self) -> None:
        """Validate corrupt cache value raises type error."""
        cache = _RecordingCache()
        req = _req("GET")
        cache._store[CacheBackend.cache_key(req)] = "not-a-response"
        mw = AsyncCacheMiddleware(cache)

        async def _noop(r: Request) -> Response:
            """Handle noop."""
            return _resp(200)

        with pytest.raises(TypeError, match="Cached value must be Response"):
            await mw.handle(req, _noop)

    async def test_cached_response_is_defensively_copied_on_read(self) -> None:
        """Validate async cache hits return copies to avoid cache contamination."""
        req = _req("GET")
        cached = Response(status_code=200, headers={"X-Test": "v1"}, content=b"ok")
        cache = _RecordingCache(prefill={CacheBackend.cache_key(req): cached})
        mw = AsyncCacheMiddleware(cache)

        first = await mw.handle(req, _AsyncCountingNextHandler(_resp(500)))
        first.headers["X-Test"] = "mutated"

        second = await mw.handle(req, _AsyncCountingNextHandler(_resp(500)))
        assert second.headers["X-Test"] == "v1"
