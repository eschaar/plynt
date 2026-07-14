"""Test ``plynth.adapters.django.drf.views``"""

from __future__ import annotations

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
