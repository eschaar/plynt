"""Test ``plynth.adapters.django.drf.views``"""

from __future__ import annotations

import asyncio
import importlib
from types import SimpleNamespace
from typing import Any, ClassVar, cast

import pytest

import plynth.adapters.django.drf.views as drf_views
from plynth.adapters.django.drf.views import (
    AsyncPlynthServiceMixin,
    CacheAliasesConfig,
    PlynthServiceMixin,
    RequestHeadersConfig,
)
from plynth.base.middleware import AsyncMiddleware
from plynth.http.settings import HTTPSettings
from plynth.http.transport import HttpxAsyncTransport, HttpxSyncTransport
from plynth.middleware.header import AsyncHeaderMiddleware, HeaderMiddleware


class _DemoSettings(HTTPSettings):
    """Provide minimal settings class for mixin tests"""


class _DemoView(PlynthServiceMixin):
    """Provide concrete test view with plynth mixin configuration"""

    settings_name = "SERVICE"
    settings_class = _DemoSettings
    cache_aliases = CacheAliasesConfig(response="responses", auth="tokens")
    request_headers = RequestHeadersConfig(enabled=False)

    def __init__(self) -> None:
        self._settings_obj = SimpleNamespace(SERVICE={"BASE_URL": "https://api"})

    def get_django_settings_object(self) -> object:
        """Return deterministic fake settings object for tests"""
        return self._settings_obj


class _AsyncDemoView(AsyncPlynthServiceMixin):
    """Provide concrete async test view with plynth mixin configuration"""

    settings_name = "SERVICE"
    settings_class = _DemoSettings
    cache_aliases = CacheAliasesConfig(response="responses", auth="tokens")
    request_headers = RequestHeadersConfig(enabled=False)

    def __init__(self) -> None:
        self._settings_obj = SimpleNamespace(SERVICE={"BASE_URL": "https://api"})

    def get_django_settings_object(self) -> object:
        """Return deterministic fake settings object for async tests"""
        return self._settings_obj


class TestPlynthServiceMixin:
    """Verify DRF service mixin behavior"""

    def test_get_django_settings_object_reads_global_settings(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Return the global Django settings object through lazy import."""
        sentinel_settings = object()
        monkeypatch.setattr(
            importlib,
            "import_module",
            lambda name: SimpleNamespace(settings=sentinel_settings),
        )

        class _ImportingView(PlynthServiceMixin):
            settings_name = "SERVICE"
            settings_class = _DemoSettings

        assert _ImportingView().get_django_settings_object() is sentinel_settings

    def test_requires_settings_name(self) -> None:
        """Raise when settings name is missing"""

        class _MissingName(PlynthServiceMixin):
            settings_name = None
            settings_class = _DemoSettings

        with pytest.raises(ValueError, match="settings_name"):
            _MissingName().get_transport()

    def test_requires_settings_class(self) -> None:
        """Raise when settings class is missing"""

        class _MissingClass(PlynthServiceMixin):
            settings_name = "SERVICE"
            settings_class = None

        with pytest.raises(ValueError, match="settings_class"):
            _MissingClass().get_transport()

    def test_builds_and_caches_transport(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Build transport once per view instance and reuse it"""
        calls: list[dict[str, Any]] = []

        def _fake_transport_from_settings(*args: object, **kwargs: object) -> object:
            calls.append({"args": args, "kwargs": kwargs})
            return object()

        monkeypatch.setattr(
            drf_views,
            "transport_from_django_settings",
            _fake_transport_from_settings,
        )

        view = _DemoView()
        first = view.get_transport()
        second = view.get_transport()

        assert first is second
        assert len(calls) == 1
        assert calls[0]["args"][0] == "SERVICE"
        assert calls[0]["kwargs"]["response_cache_alias"] == "responses"
        assert calls[0]["kwargs"]["auth_cache_alias"] == "tokens"
        assert calls[0]["kwargs"]["middlewares"] == []

    def test_injects_request_header_middleware_when_enabled(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Prepend request-header middleware when auto propagation is enabled"""
        calls: list[dict[str, Any]] = []

        def _fake_transport_from_settings(*args: object, **kwargs: object) -> object:
            calls.append({"args": args, "kwargs": kwargs})
            return object()

        monkeypatch.setattr(
            drf_views,
            "transport_from_django_settings",
            _fake_transport_from_settings,
        )

        class _AutoHeaderView(_DemoView):
            request_headers = RequestHeadersConfig(enabled=True)

            def __init__(self) -> None:
                super().__init__()
                self.request = SimpleNamespace(headers={"X-Request-Id": "req-1"})

        _AutoHeaderView().get_transport()

        middlewares = calls[0]["kwargs"]["middlewares"]
        assert len(middlewares) == 1
        assert isinstance(middlewares[0], HeaderMiddleware)

    def test_prepends_auto_header_middleware_before_custom_middlewares(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Keep auto request-header middleware ahead of custom middleware list"""
        calls: list[dict[str, Any]] = []
        custom = HeaderMiddleware({"X-Custom": "1"})

        def _fake_transport_from_settings(*args: object, **kwargs: object) -> object:
            calls.append({"args": args, "kwargs": kwargs})
            return object()

        monkeypatch.setattr(
            drf_views,
            "transport_from_django_settings",
            _fake_transport_from_settings,
        )

        class _AutoHeaderView(_DemoView):
            request_headers = RequestHeadersConfig(enabled=True)
            middlewares: ClassVar = [custom]

            def __init__(self) -> None:
                super().__init__()
                self.request = SimpleNamespace(headers={"X-Request-Id": "req-1"})

        _AutoHeaderView().get_transport()

        middlewares = calls[0]["kwargs"]["middlewares"]
        assert len(middlewares) == 2
        assert isinstance(middlewares[0], HeaderMiddleware)
        assert middlewares[1] is custom

    def test_skips_auto_header_middleware_when_request_missing(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Skip request header middleware when request is missing"""
        calls: list[dict[str, Any]] = []

        def _fake_transport_from_settings(*args: object, **kwargs: object) -> object:
            calls.append({"args": args, "kwargs": kwargs})
            return object()

        monkeypatch.setattr(
            drf_views,
            "transport_from_django_settings",
            _fake_transport_from_settings,
        )

        class _AutoHeaderView(_DemoView):
            request_headers = RequestHeadersConfig(enabled=True)

        _AutoHeaderView().get_transport()

        assert calls[0]["kwargs"]["middlewares"] == []

    def test_passes_request_headers_config_to_header_builder(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Forward request header config fields to middleware builder"""
        captured: dict[str, Any] = {}

        monkeypatch.setattr(
            drf_views,
            "build_request_header_middleware",
            lambda request, headers=None, deny_headers=None: (
                captured.update(
                    {
                        "request": request,
                        "headers": headers,
                        "deny_headers": deny_headers,
                    }
                )
                or HeaderMiddleware({})
            ),
        )

        class _AutoHeaderView(_DemoView):
            request_headers = RequestHeadersConfig(
                enabled=True,
                mapping={"X-Upstream": "X-Tenant-Id"},
                blocked={"authorization", "cookie"},
            )

            def __init__(self) -> None:
                super().__init__()
                self.request = SimpleNamespace(headers={"X-Tenant-Id": "tenant-a"})

        middleware = _AutoHeaderView().get_request_header_middleware()

        assert isinstance(middleware, HeaderMiddleware)
        assert captured["headers"] == {"X-Upstream": "X-Tenant-Id"}
        assert captured["deny_headers"] == {"authorization", "cookie"}

    def test_get_request_header_middleware_returns_none_when_disabled(self) -> None:
        """Return no sync middleware when request-header propagation is disabled."""
        assert _DemoView().get_request_header_middleware() is None

    def test_get_service_builds_and_caches_named_services(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Build named service lazily and reuse cached instance"""
        transport = object()
        monkeypatch.setattr(
            _DemoView,
            "get_transport",
            lambda self: transport,
        )

        class _ServiceView(_DemoView):
            service_factories: ClassVar = {
                "catalog": lambda t: {"transport": t, "name": "catalog"}
            }

        view = _ServiceView()
        first = view.get_service("catalog")
        second = view.get_service("catalog")

        assert first is second
        assert first["transport"] is transport

    def test_get_client_aliases_named_service(self) -> None:
        """Return default client service through get_client"""

        class _ClientView(_DemoView):
            service_factories: ClassVar = {
                "client": lambda t: {"transport": t, "name": "client"}
            }

            def get_transport(self) -> HttpxSyncTransport:
                return cast(HttpxSyncTransport, object())

        view = _ClientView()
        client = view.get_client()

        assert client["name"] == "client"

    def test_finalize_response_closes_cached_transport(self) -> None:
        """Close the cached transport after the response is finalized"""
        close_calls = {"value": 0}

        class _FinalizeView(PlynthServiceMixin):
            settings_name = "SERVICE"
            settings_class = _DemoSettings

            def __init__(self) -> None:
                self._transport = cast(Any, SimpleNamespace(close=_close))

        def _close() -> None:
            close_calls["value"] += 1

        view = _FinalizeView()

        response = object()

        assert view.finalize_response(object(), response) is response
        assert close_calls["value"] == 1
        assert "_transport" not in view.__dict__

    def test_finalize_response_uses_super_when_available(self) -> None:
        """Delegate to parent finalize_response when class MRO provides it."""

        class _ParentFinalize:
            def finalize_response(
                self,
                request: object,
                response: object,
                *args: object,
                **kwargs: object,
            ) -> object:
                del request, args, kwargs
                return response

        class _FinalizeView(PlynthServiceMixin, _ParentFinalize):
            settings_name = "SERVICE"
            settings_class = _DemoSettings

            def __init__(self) -> None:
                self._transport = cast(Any, SimpleNamespace(close=lambda: None))

        view = _FinalizeView()
        sentinel = object()

        assert view.finalize_response(object(), sentinel) is sentinel

    def test_close_cached_transport_is_noop_without_transport(self) -> None:
        """Return silently when no cached transport exists."""
        view = _DemoView()
        cast(Any, getattr(view, "_close_cached_transport"))()  # noqa: B009
        assert "_transport" not in view.__dict__

    def test_close_cached_transport_ignores_delattr_attribute_error(self) -> None:
        """Do not fail when deleting cached transport raises AttributeError."""

        class _DeleteFailsView(_DemoView):
            def __delattr__(self, name: str) -> None:
                raise AttributeError(name)

        close_calls = {"value": 0}
        view = _DeleteFailsView()
        transport = SimpleNamespace(close=lambda: close_calls.__setitem__("value", 1))
        object.__setattr__(
            view,
            "_transport",
            cast(Any, transport),
        )

        cast(Any, getattr(view, "_close_cached_transport"))()  # noqa: B009

        assert close_calls["value"] == 1

    def test_transport_is_not_reused_across_distinct_view_instances(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Build separate transports for separate view instances"""
        call_count = {"value": 0}

        def _fake_transport_from_settings(*_args: object, **_kwargs: object) -> object:
            call_count["value"] += 1
            return object()

        monkeypatch.setattr(
            drf_views,
            "transport_from_django_settings",
            _fake_transport_from_settings,
        )

        first_view = _DemoView()
        second_view = _DemoView()

        first_transport = first_view.get_transport()
        second_transport = second_view.get_transport()

        assert first_transport is not second_transport
        assert call_count["value"] == 2

    def test_named_service_is_not_reused_across_distinct_view_instances(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Build separate named services for separate view instances"""

        def _fake_transport_from_settings(*_args: object, **_kwargs: object) -> object:
            return object()

        monkeypatch.setattr(
            drf_views,
            "transport_from_django_settings",
            _fake_transport_from_settings,
        )

        class _ServiceView(_DemoView):
            service_factories: ClassVar = {
                "client": lambda t: {"transport": t, "name": "client"}
            }

        first_view = _ServiceView()
        second_view = _ServiceView()

        first_client = first_view.get_client()
        second_client = second_view.get_client()

        assert first_client is not second_client
        assert first_client["transport"] is not second_client["transport"]

    def test_get_service_raises_for_unknown_name(self) -> None:
        """Raise with available names when requested service is unknown"""
        view = _DemoView()

        with pytest.raises(KeyError, match="Unknown plynth service"):
            view.get_service("missing")


class _AsyncCustomMiddleware(AsyncMiddleware):
    """Provide async middleware stub for ordering checks"""

    async def handle(self, request: Any, next_handler: Any) -> Any:
        """Pass control to the next middleware or transport handler"""
        return await next_handler(request)


class TestAsyncPlynthServiceMixin:
    """Verify async DRF service mixin behavior"""

    def test_requires_settings_name(self) -> None:
        """Raise when settings name is missing"""

        class _MissingName(AsyncPlynthServiceMixin):
            settings_name = None
            settings_class = _DemoSettings

        with pytest.raises(ValueError, match="settings_name"):
            _MissingName().get_transport()

    def test_requires_settings_class(self) -> None:
        """Raise when settings class is missing"""

        class _MissingClass(AsyncPlynthServiceMixin):
            settings_name = "SERVICE"
            settings_class = None

        with pytest.raises(ValueError, match="settings_class"):
            _MissingClass().get_transport()

    def test_builds_and_caches_transport(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Build async transport once per view instance and reuse it"""
        calls: list[dict[str, Any]] = []

        def _fake_async_transport_from_settings(
            *args: object, **kwargs: object
        ) -> object:
            calls.append({"args": args, "kwargs": kwargs})
            return object()

        monkeypatch.setattr(
            drf_views,
            "async_transport_from_django_settings",
            _fake_async_transport_from_settings,
        )

        view = _AsyncDemoView()
        first = view.get_transport()
        second = view.get_transport()

        assert first is second
        assert len(calls) == 1
        assert calls[0]["args"][0] == "SERVICE"
        assert calls[0]["kwargs"]["response_cache_alias"] == "responses"
        assert calls[0]["kwargs"]["auth_cache_alias"] == "tokens"
        assert calls[0]["kwargs"]["middlewares"] == []

    def test_injects_request_header_middleware_when_enabled(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Prepend async request-header middleware when auto propagation is enabled"""
        calls: list[dict[str, Any]] = []

        def _fake_async_transport_from_settings(
            *args: object, **kwargs: object
        ) -> object:
            calls.append({"args": args, "kwargs": kwargs})
            return object()

        monkeypatch.setattr(
            drf_views,
            "async_transport_from_django_settings",
            _fake_async_transport_from_settings,
        )

        class _AutoHeaderView(_AsyncDemoView):
            request_headers = RequestHeadersConfig(enabled=True)

            def __init__(self) -> None:
                super().__init__()
                self.request = SimpleNamespace(headers={"X-Request-Id": "req-1"})

        _AutoHeaderView().get_transport()

        middlewares = calls[0]["kwargs"]["middlewares"]
        assert len(middlewares) == 1
        assert isinstance(middlewares[0], AsyncHeaderMiddleware)

    def test_prepends_auto_header_middleware_before_custom_middlewares(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Keep async auto request-header middleware ahead of custom middleware list"""
        calls: list[dict[str, Any]] = []
        custom = _AsyncCustomMiddleware()

        def _fake_async_transport_from_settings(
            *args: object, **kwargs: object
        ) -> object:
            calls.append({"args": args, "kwargs": kwargs})
            return object()

        monkeypatch.setattr(
            drf_views,
            "async_transport_from_django_settings",
            _fake_async_transport_from_settings,
        )

        class _AutoHeaderView(_AsyncDemoView):
            request_headers = RequestHeadersConfig(enabled=True)
            middlewares: ClassVar = [custom]

            def __init__(self) -> None:
                super().__init__()
                self.request = SimpleNamespace(headers={"X-Request-Id": "req-1"})

        _AutoHeaderView().get_transport()

        middlewares = calls[0]["kwargs"]["middlewares"]
        assert len(middlewares) == 2
        assert isinstance(middlewares[0], AsyncHeaderMiddleware)
        assert middlewares[1] is custom

    def test_passes_request_headers_config_to_async_header_builder(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Forward request header config fields to async middleware builder"""
        captured: dict[str, Any] = {}

        monkeypatch.setattr(
            drf_views,
            "build_async_request_header_middleware",
            lambda request, headers=None, deny_headers=None: (
                captured.update(
                    {
                        "request": request,
                        "headers": headers,
                        "deny_headers": deny_headers,
                    }
                )
                or AsyncHeaderMiddleware({})
            ),
        )

        class _AutoHeaderView(_AsyncDemoView):
            request_headers = RequestHeadersConfig(
                enabled=True,
                mapping={"X-Upstream": "X-Tenant-Id"},
                blocked={"authorization", "cookie"},
            )

            def __init__(self) -> None:
                super().__init__()
                self.request = SimpleNamespace(headers={"X-Tenant-Id": "tenant-a"})

        middleware = _AutoHeaderView().get_request_header_middleware()

        assert isinstance(middleware, AsyncHeaderMiddleware)
        assert captured["headers"] == {"X-Upstream": "X-Tenant-Id"}
        assert captured["deny_headers"] == {"authorization", "cookie"}

    def test_get_request_header_middleware_returns_none_when_disabled(self) -> None:
        """Return no async middleware when request-header propagation is disabled."""
        assert _AsyncDemoView().get_request_header_middleware() is None

    def test_skips_auto_header_middleware_when_request_missing(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Do not inject async request header middleware without a request."""
        calls: list[dict[str, Any]] = []

        def _fake_async_transport_from_settings(
            *args: object, **kwargs: object
        ) -> object:
            calls.append({"args": args, "kwargs": kwargs})
            return object()

        monkeypatch.setattr(
            drf_views,
            "async_transport_from_django_settings",
            _fake_async_transport_from_settings,
        )

        class _AutoHeaderView(_AsyncDemoView):
            request_headers = RequestHeadersConfig(enabled=True)

        _AutoHeaderView().get_transport()

        assert calls[0]["kwargs"]["middlewares"] == []

    def test_get_service_builds_and_caches_named_services(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Build named async service lazily and reuse cached instance"""
        transport = object()
        monkeypatch.setattr(
            _AsyncDemoView,
            "get_transport",
            lambda self: transport,
        )

        class _ServiceView(_AsyncDemoView):
            service_factories: ClassVar = {
                "catalog": lambda t: {"transport": t, "name": "catalog"}
            }

        view = _ServiceView()
        first = view.get_service("catalog")
        second = view.get_service("catalog")

        assert first is second
        assert first["transport"] is transport

    def test_get_client_aliases_named_service(self) -> None:
        """Return default async client service through get_client"""

        class _ClientView(_AsyncDemoView):
            service_factories: ClassVar = {
                "client": lambda t: {"transport": t, "name": "client"}
            }

            def get_transport(self) -> HttpxAsyncTransport:
                return cast(HttpxAsyncTransport, object())

        view = _ClientView()
        client = view.get_client()

        assert client["name"] == "client"

    def test_finalize_response_closes_cached_async_transport(self) -> None:
        """Close the cached async transport after the response is finalized"""
        close_calls = {"value": 0}

        class _FinalizeView(AsyncPlynthServiceMixin):
            settings_name = "SERVICE"
            settings_class = _DemoSettings

            def __init__(self) -> None:
                self._transport = cast(Any, SimpleNamespace(aclose=self._aclose))

            async def _aclose(self) -> None:
                close_calls["value"] += 1

        view = _FinalizeView()
        response = object()

        assert view.finalize_response(object(), response) is response
        assert close_calls["value"] == 1
        assert "_transport" not in view.__dict__

    def test_finalize_response_uses_super_when_available(self) -> None:
        """Delegate to parent finalize_response when class MRO provides it."""

        class _ParentFinalize:
            def finalize_response(
                self,
                request: object,
                response: object,
                *args: object,
                **kwargs: object,
            ) -> object:
                del request, args, kwargs
                return response

        class _FinalizeView(AsyncPlynthServiceMixin, _ParentFinalize):
            settings_name = "SERVICE"
            settings_class = _DemoSettings

            def __init__(self) -> None:
                self._transport = cast(Any, SimpleNamespace(aclose=self._aclose))

            async def _aclose(self) -> None:
                return None

        view = _FinalizeView()
        sentinel = object()

        assert view.finalize_response(object(), sentinel) is sentinel

    def test_aclose_cached_transport_is_noop_without_transport(self) -> None:
        """Return silently when no async cached transport exists."""
        view = _AsyncDemoView()
        asyncio.run(
            cast(Any, getattr(view, "_aclose_cached_transport"))()  # noqa: B009
        )
        assert "_transport" not in view.__dict__

    def test_aclose_cached_transport_falls_back_to_sync_close(self) -> None:
        """Use sync close path when async close is unavailable."""
        close_calls = {"value": 0}

        class _SyncCloseView(_AsyncDemoView):
            def __init__(self) -> None:
                super().__init__()
                self._transport = cast(
                    Any,
                    SimpleNamespace(close=lambda: close_calls.__setitem__("value", 1)),
                )

        view = _SyncCloseView()
        asyncio.run(
            cast(Any, getattr(view, "_aclose_cached_transport"))()  # noqa: B009
        )

        assert close_calls["value"] == 1
        assert "_transport" not in view.__dict__

    def test_aclose_cached_transport_ignores_delattr_attribute_error(self) -> None:
        """Do not fail when async cleanup cannot delete cached transport."""

        class _DeleteFailsAsyncView(_AsyncDemoView):
            def __init__(self) -> None:
                super().__init__()
                self._transport = cast(Any, SimpleNamespace(aclose=self._aclose))

            async def _aclose(self) -> None:
                return None

            def __delattr__(self, name: str) -> None:
                raise AttributeError(name)

        delete_fails_view = _DeleteFailsAsyncView()
        asyncio.run(
            cast(Any, getattr(delete_fails_view, "_aclose_cached_transport"))()  # noqa: B009
        )

    @pytest.mark.asyncio
    async def test_finalize_response_handles_running_event_loop_cleanup(self) -> None:
        """Schedule cleanup task when finalize_response runs inside event loop."""
        close_calls = {"value": 0}

        class _FinalizeInLoopView(AsyncPlynthServiceMixin):
            settings_name = "SERVICE"
            settings_class = _DemoSettings

            def __init__(self) -> None:
                self._transport = cast(Any, SimpleNamespace(aclose=self._aclose))

            async def _aclose(self) -> None:
                close_calls["value"] += 1

        view = _FinalizeInLoopView()

        response = object()
        assert view.finalize_response(object(), response) is response
        await asyncio.sleep(0)

        assert close_calls["value"] == 1

    def test_finalize_response_reraises_unexpected_runtime_error(self) -> None:
        """Re-raise runtime errors that are not loop-state related."""

        class _FinalizeView(AsyncPlynthServiceMixin):
            settings_name = "SERVICE"
            settings_class = _DemoSettings

            def __init__(self) -> None:
                self._transport = cast(Any, SimpleNamespace(aclose=self._aclose))

            async def _aclose(self) -> None:
                return None

        view = _FinalizeView()

        original_run = asyncio.run

        def _raise(*_args: object, **_kwargs: object) -> None:
            if _args and asyncio.iscoroutine(_args[0]):
                _args[0].close()
            raise RuntimeError("boom")

        asyncio_module = cast(Any, asyncio)
        asyncio_module.run = _raise
        try:
            with pytest.raises(RuntimeError, match="boom"):
                view.finalize_response(object(), object())
        finally:
            asyncio_module.run = original_run

    def test_transport_is_not_reused_across_distinct_view_instances(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Build separate async transports for separate view instances"""
        call_count = {"value": 0}

        def _fake_async_transport_from_settings(
            *_args: object, **_kwargs: object
        ) -> object:
            call_count["value"] += 1
            return object()

        monkeypatch.setattr(
            drf_views,
            "async_transport_from_django_settings",
            _fake_async_transport_from_settings,
        )

        first_view = _AsyncDemoView()
        second_view = _AsyncDemoView()

        first_transport = first_view.get_transport()
        second_transport = second_view.get_transport()

        assert first_transport is not second_transport
        assert call_count["value"] == 2

    def test_named_service_is_not_reused_across_distinct_view_instances(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Build separate named async services for separate view instances"""

        def _fake_async_transport_from_settings(
            *_args: object, **_kwargs: object
        ) -> object:
            return object()

        monkeypatch.setattr(
            drf_views,
            "async_transport_from_django_settings",
            _fake_async_transport_from_settings,
        )

        class _ServiceView(_AsyncDemoView):
            service_factories: ClassVar = {
                "client": lambda t: {"transport": t, "name": "client"}
            }

        first_view = _ServiceView()
        second_view = _ServiceView()

        first_client = first_view.get_client()
        second_client = second_view.get_client()

        assert first_client is not second_client
        assert first_client["transport"] is not second_client["transport"]

    def test_get_service_raises_for_unknown_name(self) -> None:
        """Raise with available names when requested async service is unknown"""
        view = _AsyncDemoView()

        with pytest.raises(KeyError, match="Unknown plynth service"):
            view.get_service("missing")
