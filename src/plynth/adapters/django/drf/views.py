"""DRF view integration helpers for Plynth."""

from __future__ import annotations

import importlib
from collections.abc import Callable
from typing import Any, ClassVar, cast

from plynth.adapters.django.transport import transport_from_django_settings
from plynth.base.middleware import SyncMiddleware
from plynth.http.settings import HTTPSettings
from plynth.http.transport import HttpxSyncTransport

__all__ = ["PlynthServiceMixin"]


ServiceFactory = Callable[[HttpxSyncTransport], Any]


class PlynthServiceMixin:
    """Mixin for building plynth transports/services inside DRF views.

    Configure class attributes in a concrete APIView/ViewSet:

    1. ``plynth_settings_name``: Django settings attribute name.
    1. ``plynth_settings_class``: ``HTTPSettings`` subclass.
    1. Optionally cache aliases and extra middleware.
    1. Optionally ``plynth_service_factories`` for named service factories.

    The mixin lazily builds and caches one transport per view instance.
    """

    plynth_settings_name: ClassVar[str | None] = None
    plynth_settings_class: ClassVar[type[HTTPSettings] | None] = None
    plynth_response_cache_alias: ClassVar[str | None] = None
    plynth_auth_cache_alias: ClassVar[str | None] = None
    plynth_middlewares: ClassVar[list[SyncMiddleware] | None] = None
    plynth_service_factories: ClassVar[dict[str, ServiceFactory] | None] = None

    def get_django_settings_object(self) -> object:
        """Return Django's global settings object lazily."""
        django_conf = importlib.import_module("django.conf")
        return django_conf.settings

    def get_plynth_transport(self) -> HttpxSyncTransport:
        """Return a cached plynth transport for this view instance."""
        cached_transport = getattr(self, "_plynth_transport", None)
        if cached_transport is not None:
            return cast(HttpxSyncTransport, cached_transport)

        if self.plynth_settings_name is None:
            raise ValueError("plynth_settings_name must be configured on the view")
        if self.plynth_settings_class is None:
            raise ValueError("plynth_settings_class must be configured on the view")

        transport = transport_from_django_settings(
            self.plynth_settings_name,
            self.plynth_settings_class,
            settings_obj=self.get_django_settings_object(),
            response_cache_alias=self.plynth_response_cache_alias,
            auth_cache_alias=self.plynth_auth_cache_alias,
            middlewares=list(self.plynth_middlewares or []),
        )
        self._plynth_transport = transport
        return transport

    def get_plynth_service_factories(self) -> dict[str, ServiceFactory]:
        """Return named service factories configured on this view."""
        return dict(self.plynth_service_factories or {})

    def get_plynth_service(self, name: str) -> Any:
        """Return one lazily-created named service instance."""
        cached_services = getattr(self, "_plynth_services", None)
        if not isinstance(cached_services, dict):
            cached_services = {}
            self._plynth_services = cached_services

        if name in cached_services:
            return cached_services[name]

        factories = self.get_plynth_service_factories()
        if name not in factories:
            available = ", ".join(sorted(factories)) if factories else "none"
            raise KeyError(f"Unknown plynth service {name!r}; available: {available}")

        service = factories[name](self.get_plynth_transport())
        cached_services[name] = service
        return service

    def get_client(self, name: str = "client") -> Any:
        """Return a named upstream client/service.

        This is a convenience alias for ``get_plynth_service(...)``.

        Args:
            name: Service key from ``plynth_service_factories``.
                Defaults to ``"client"``.

        """
        return self.get_plynth_service(name)
