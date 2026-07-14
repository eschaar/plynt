"""Tests for ``plynth.adapters.django.drf.views``."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, ClassVar, cast

import pytest

import plynth.adapters.django.drf.views as drf_views
from plynth.adapters.django.drf.views import PlynthServiceMixin
from plynth.http.settings import HTTPSettings
from plynth.http.transport import HttpxSyncTransport
from plynth.middleware.header import HeaderMiddleware


class _DemoSettings(HTTPSettings):
    """Minimal settings class for mixin tests."""


class _DemoView(PlynthServiceMixin):
    """Concrete test view that configures plynth mixin attributes."""

    plynth_settings_name = "SERVICE"
    plynth_settings_class = _DemoSettings
    plynth_response_cache_alias = "responses"
    plynth_auth_cache_alias = "tokens"
    plynth_auto_request_headers = False

    def __init__(self) -> None:
        self._settings_obj = SimpleNamespace(SERVICE={"BASE_URL": "https://api"})

    def get_django_settings_object(self) -> object:
        """Return deterministic fake settings object for tests."""
        return self._settings_obj


class TestPlynthServiceMixin:
    """Verify DRF service mixin behavior."""

    def test_requires_settings_name(self) -> None:
        """Raise when settings name is missing."""

        class _MissingName(PlynthServiceMixin):
            plynth_settings_name = None
            plynth_settings_class = _DemoSettings

        with pytest.raises(ValueError, match="plynth_settings_name"):
            _MissingName().get_plynth_transport()

    def test_requires_settings_class(self) -> None:
        """Raise when settings class is missing."""

        class _MissingClass(PlynthServiceMixin):
            plynth_settings_name = "SERVICE"
            plynth_settings_class = None

        with pytest.raises(ValueError, match="plynth_settings_class"):
            _MissingClass().get_plynth_transport()

    def test_builds_and_caches_transport(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Build transport once per view instance and reuse it."""
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
        first = view.get_plynth_transport()
        second = view.get_plynth_transport()

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
        """Prepend request-header middleware when auto propagation is enabled."""
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
            plynth_auto_request_headers = True

            def __init__(self) -> None:
                super().__init__()
                self.request = SimpleNamespace(headers={"X-Request-Id": "req-1"})

        _AutoHeaderView().get_plynth_transport()

        middlewares = calls[0]["kwargs"]["middlewares"]
        assert len(middlewares) == 1
        assert isinstance(middlewares[0], HeaderMiddleware)

    def test_prepends_auto_header_middleware_before_custom_middlewares(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Keep auto request-header middleware ahead of custom middleware list."""
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
            plynth_auto_request_headers = True
            plynth_middlewares: ClassVar = [custom]

            def __init__(self) -> None:
                super().__init__()
                self.request = SimpleNamespace(headers={"X-Request-Id": "req-1"})

        _AutoHeaderView().get_plynth_transport()

        middlewares = calls[0]["kwargs"]["middlewares"]
        assert len(middlewares) == 2
        assert isinstance(middlewares[0], HeaderMiddleware)
        assert middlewares[1] is custom

    def test_skips_auto_header_middleware_when_request_missing(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Do not inject request header middleware when no request is available."""
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
            plynth_auto_request_headers = True

        _AutoHeaderView().get_plynth_transport()

        assert calls[0]["kwargs"]["middlewares"] == []

    def test_get_plynth_service_builds_and_caches_named_services(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Build named service lazily and reuse cached instance."""
        transport = object()
        monkeypatch.setattr(
            _DemoView,
            "get_plynth_transport",
            lambda self: transport,
        )

        class _ServiceView(_DemoView):
            plynth_service_factories: ClassVar = {
                "catalog": lambda t: {"transport": t, "name": "catalog"}
            }

        view = _ServiceView()
        first = view.get_plynth_service("catalog")
        second = view.get_plynth_service("catalog")

        assert first is second
        assert first["transport"] is transport

    def test_get_client_aliases_named_service(self) -> None:
        """Return the default 'client' service through get_client()."""

        class _ClientView(_DemoView):
            plynth_service_factories: ClassVar = {
                "client": lambda t: {"transport": t, "name": "client"}
            }

            def get_plynth_transport(self) -> HttpxSyncTransport:
                return cast(HttpxSyncTransport, object())

        view = _ClientView()
        client = view.get_client()

        assert client["name"] == "client"

    def test_transport_is_not_reused_across_distinct_view_instances(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Build separate transports for separate view instances."""
        call_count = {"value": 0}

        def _fake_transport_from_settings(*args: object, **kwargs: object) -> object:
            call_count["value"] += 1
            return object()

        monkeypatch.setattr(
            drf_views,
            "transport_from_django_settings",
            _fake_transport_from_settings,
        )

        first_view = _DemoView()
        second_view = _DemoView()

        first_transport = first_view.get_plynth_transport()
        second_transport = second_view.get_plynth_transport()

        assert first_transport is not second_transport
        assert call_count["value"] == 2

    def test_named_service_is_not_reused_across_distinct_view_instances(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Build separate named services for separate view instances."""

        def _fake_transport_from_settings(*args: object, **kwargs: object) -> object:
            return object()

        monkeypatch.setattr(
            drf_views,
            "transport_from_django_settings",
            _fake_transport_from_settings,
        )

        class _ServiceView(_DemoView):
            plynth_service_factories: ClassVar = {
                "client": lambda t: {"transport": t, "name": "client"}
            }

        first_view = _ServiceView()
        second_view = _ServiceView()

        first_client = first_view.get_client()
        second_client = second_view.get_client()

        assert first_client is not second_client
        assert first_client["transport"] is not second_client["transport"]

    def test_get_plynth_service_raises_for_unknown_name(self) -> None:
        """Raise with available names when requested service is unknown."""
        view = _DemoView()

        with pytest.raises(KeyError, match="Unknown plynth service"):
            view.get_plynth_service("missing")
