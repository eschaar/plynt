"""Executable smoke tests for Django DRF adapter helpers."""

from __future__ import annotations

import importlib
from typing import ClassVar, cast

import pytest

from plynth.adapters.django.drf.views import PlynthServiceMixin
from plynth.http.settings import HTTPSettings
from plynth.http.transport import HttpxSyncTransport

django = pytest.importorskip("django")
pytest.importorskip("rest_framework")

django_settings = importlib.import_module("django.conf").settings
override_settings = importlib.import_module("django.test.utils").override_settings
APIView = importlib.import_module("rest_framework.views").APIView

if not django_settings.configured:
    django_settings.configure(
        SECRET_KEY="smoke-tests",
        USE_TZ=True,
        INSTALLED_APPS=["rest_framework"],
        MIDDLEWARE=[],
    )
    django.setup()


class _SmokeSettings(HTTPSettings):
    """Minimal HTTP settings model for DRF mixin smoke checks."""


class _SmokeView(PlynthServiceMixin):
    """Concrete mixin config that can be combined with DRF APIView."""

    plynth_settings_name = "SERVICE"
    plynth_settings_class = _SmokeSettings
    plynth_service_factories: ClassVar = {
        "client": lambda transport: {"transport": transport, "name": "client"}
    }


def _build_view() -> PlynthServiceMixin:
    """Create a concrete DRF APIView + PlynthServiceMixin instance."""
    smoke_api_view_cls = type("_SmokeAPIView", (_SmokeView, APIView), {})
    return cast(PlynthServiceMixin, smoke_api_view_cls())


class TestDjangoDRFAdapterSmoke:
    """Run fast runtime checks for DRF integration helpers."""

    def test_mixin_builds_transport_and_client_without_monkeypatch(self) -> None:
        """Build one transport and one named client through real helpers."""
        with override_settings(SERVICE={"BASE_URL": "https://api.example.test"}):
            view = _build_view()

            transport = view.get_plynth_transport()
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
