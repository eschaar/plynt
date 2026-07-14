"""Executable smoke tests for Django adapter helpers."""

from __future__ import annotations

import importlib

import pytest

from plynth.adapters.django.transport import (
    async_transport_from_django_settings,
    transport_from_django_settings,
)
from plynth.http.settings import HTTPSettings
from plynth.http.transport import HttpxAsyncTransport, HttpxSyncTransport
from plynth.middleware.retry import AsyncRetryMiddleware, RetryMiddleware

django = pytest.importorskip("django")
django_settings = importlib.import_module("django.conf").settings

if not django_settings.configured:
    django_settings.configure(
        SECRET_KEY="smoke-tests",
        USE_TZ=True,
        INSTALLED_APPS=[],
        MIDDLEWARE=[],
    )
    django.setup()


class _SmokeSettings(HTTPSettings):
    """Minimal settings model for smoke-level transport wiring checks."""


class TestDjangoAdapterSmoke:
    """Run fast runtime checks for Django adapter integration points."""

    def test_transport_from_django_settings_builds_real_transport(self) -> None:
        """Build a concrete transport from real Django settings."""
        previous = getattr(django_settings, "SERVICE", None)
        had_previous = hasattr(django_settings, "SERVICE")
        django_settings.SERVICE = {
            "BASE_URL": "https://api.example.test",
            "MAX_ATTEMPTS": 3,
        }

        try:
            transport = transport_from_django_settings(
                "SERVICE",
                _SmokeSettings,
                settings_obj=django_settings,
            )
            assert isinstance(transport, HttpxSyncTransport)
            assert len(transport._middlewares) == 1  # pylint: disable=protected-access
            assert isinstance(
                transport._middlewares[0],  # pylint: disable=protected-access
                RetryMiddleware,
            )
        finally:
            transport.close()
            if had_previous:
                django_settings.SERVICE = previous
            else:
                delattr(django_settings, "SERVICE")

    @pytest.mark.asyncio
    async def test_async_transport_from_django_settings_builds_real_transport(
        self,
    ) -> None:
        """Build a concrete async transport from real Django settings."""
        previous = getattr(django_settings, "SERVICE", None)
        had_previous = hasattr(django_settings, "SERVICE")
        django_settings.SERVICE = {
            "BASE_URL": "https://api.example.test",
            "MAX_ATTEMPTS": 3,
        }

        try:
            transport = async_transport_from_django_settings(
                "SERVICE",
                _SmokeSettings,
                settings_obj=django_settings,
            )
        finally:
            if had_previous:
                django_settings.SERVICE = previous
            else:
                delattr(django_settings, "SERVICE")

        try:
            assert isinstance(transport, HttpxAsyncTransport)
            assert len(transport._middlewares) == 1  # pylint: disable=protected-access
            assert isinstance(
                transport._middlewares[0],  # pylint: disable=protected-access
                AsyncRetryMiddleware,
            )
        finally:
            await transport.aclose()
