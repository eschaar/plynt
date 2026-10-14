"""Executable smoke tests for Django DRF adapter helpers."""

from __future__ import annotations

import importlib
from typing import ClassVar, cast

import pytest

from plynt.adapters.django.drf.views import AsyncPlyntServiceMixin, PlyntServiceMixin
from plynt.http.settings import HTTPSettings
from plynt.http.transport import HttpxAsyncTransport, HttpxSyncTransport

django = pytest.importorskip("django")

django_settings = importlib.import_module("django.conf").settings

if not django_settings.configured:
    django_settings.configure(
        SECRET_KEY="smoke-tests",
        USE_TZ=True,
        INSTALLED_APPS=["rest_framework"],
        MIDDLEWARE=[],
    )
    django.setup()

pytest.importorskip("rest_framework")

override_settings = importlib.import_module("django.test.utils").override_settings
APIView = importlib.import_module("rest_framework.views").APIView


class _SmokeSettings(HTTPSettings):
    """Minimal HTTP settings model for DRF mixin smoke checks."""


class _SmokeView(PlyntServiceMixin):
    """Concrete mixin config that can be combined with DRF APIView."""

    settings_name = "SERVICE"
    settings_class = _SmokeSettings
    service_factories: ClassVar = {
        "client": lambda transport: {"transport": transport, "name": "client"}
    }


class _AsyncSmokeView(AsyncPlyntServiceMixin):
    """Concrete async mixin config that can be combined with DRF APIView."""

    settings_name = "SERVICE"
    settings_class = _SmokeSettings
    service_factories: ClassVar = {
        "client": lambda transport: {"transport": transport, "name": "client"}
    }


def _build_view() -> PlyntServiceMixin:
    """Create a concrete DRF APIView + PlyntServiceMixin instance."""
    smoke_api_view_cls = type("_SmokeAPIView", (_SmokeView, APIView), {})
    return cast(PlyntServiceMixin, smoke_api_view_cls())


def _build_async_view() -> AsyncPlyntServiceMixin:
    """Create a concrete DRF APIView + AsyncPlyntServiceMixin instance."""
    smoke_api_view_cls = type("_AsyncSmokeAPIView", (_AsyncSmokeView, APIView), {})
    return cast(AsyncPlyntServiceMixin, smoke_api_view_cls())


class TestDjangoDRFAdapterSmoke:
    """Run fast runtime checks for DRF integration helpers."""

    def test_mixin_builds_transport_and_client_without_monkeypatch(self) -> None:
        """Build one transport and one named client through real helpers."""
        with override_settings(SERVICE={"BASE_URL": "https://api.example.test"}):
            view = _build_view()

            transport = view.get_transport()
            client = view.get_client()

        assert isinstance(transport, HttpxSyncTransport)
        assert client["name"] == "client"
        assert client["transport"] is transport

    def test_get_client_reuses_cached_named_service(self) -> None:
        """Return same service instance on repeated get_client calls."""
        with override_settings(SERVICE={"BASE_URL": "https://api.example.test"}):
            view = _build_view()

            first = cast(object, view.get_client())
            second = cast(object, view.get_client())

        assert first is second

    @pytest.mark.asyncio
    async def test_async_mixin_builds_transport_and_client_without_monkeypatch(
        self,
    ) -> None:
        """Build one async transport and one named client through real helpers."""
        with override_settings(SERVICE={"BASE_URL": "https://api.example.test"}):
            view = _build_async_view()

            transport = view.get_transport()
            client = view.get_client()

        try:
            assert isinstance(transport, HttpxAsyncTransport)
            assert client["name"] == "client"
            assert client["transport"] is transport
        finally:
            await transport.aclose()
