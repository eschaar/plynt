"""Provide DRF view integration helpers for Plynt"""

from __future__ import annotations

import asyncio
import importlib
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, ClassVar, TypedDict, cast

from plynt.adapters.django.drf.headers import (
    build_async_request_header_middleware,
    build_request_header_middleware,
)
from plynt.adapters.django.transport import (
    async_transport_from_django_settings,
    transport_from_django_settings,
)
from plynt.base.middleware import AsyncMiddleware, SyncMiddleware
from plynt.http.settings import HTTPSettings
from plynt.http.transport import HttpxAsyncTransport, HttpxSyncTransport

__all__ = [
    "AsyncPlyntServiceMixin",
    "CacheAliasesConfig",
    "PlyntServiceMixin",
    "RequestHeadersConfig",
]


SyncServiceFactory = Callable[[HttpxSyncTransport], Any]
AsyncServiceFactory = Callable[[HttpxAsyncTransport], Any]


_background_transport_cleanup_tasks: set[asyncio.Task[Any]] = set()


@dataclass(frozen=True)
class RequestHeadersConfig:
    """Define inbound-to-outbound request header propagation config"""

    enabled: bool = False
    mapping: dict[str, str] | None = None
    blocked: set[str] | None = None


@dataclass(frozen=True)
class CacheAliasesConfig:
    """Define cache alias config for response and auth concerns"""

    response: str | None = None
    auth: str | None = None


class _RequestHeaderBuilderKwargs(TypedDict):
    """Type request-header middleware builder kwargs"""

    request: object
    headers: dict[str, str] | None
    deny_headers: set[str] | None


class _BasePlyntServiceMixin:
    """Share common DRF adapter config and cache helpers

    Subclasses bind the execution model by choosing sync or async transport and
    middleware builders.
    """

    settings_name: ClassVar[str | None] = None
    settings_class: ClassVar[type[HTTPSettings] | None] = None
    cache_aliases: ClassVar[CacheAliasesConfig] = CacheAliasesConfig()
    request_headers: ClassVar[RequestHeadersConfig] = RequestHeadersConfig()

    def get_django_settings_object(self) -> object:
        """Return Django's global settings object lazily"""
        django_conf = importlib.import_module("django.conf")
        return django_conf.settings

    def _get_transport_settings(self) -> tuple[str, type[HTTPSettings]]:
        """Return validated transport settings configuration"""
        if self.settings_name is None:
            raise ValueError("settings_name must be configured on the view")
        if self.settings_class is None:
            raise ValueError("settings_class must be configured on the view")
        return self.settings_name, self.settings_class

    def _get_request_header_builder_kwargs(
        self,
    ) -> _RequestHeaderBuilderKwargs | None:
        """Return resolved kwargs for request-header middleware builders"""
        config = self.request_headers
        if not config.enabled:
            return None

        request = getattr(self, "request", None)
        if request is None:
            return None

        return {
            "request": request,
            "headers": dict(config.mapping) if config.mapping is not None else None,
            "deny_headers": (
                set(config.blocked) if config.blocked is not None else None
            ),
        }

    def _get_service_cache(self) -> dict[str, Any]:
        """Return per-view cache for lazily built named services"""
        cached_services = getattr(self, "_services", None)
        if not isinstance(cached_services, dict):
            cached_services = {}
            self._services = cached_services
        return cast(dict[str, Any], cached_services)

    def _close_cached_transport(self) -> None:
        """Close and discard a cached transport when one exists"""
        cached_transport = getattr(self, "_transport", None)
        if cached_transport is None:
            return

        close = getattr(cached_transport, "close", None)
        if close is not None:
            cast(Any, close)()

        try:
            delattr(self, "_transport")
        except AttributeError:
            pass

    async def _aclose_cached_transport(self) -> None:
        """Async-close and discard a cached transport when one exists"""
        cached_transport = getattr(self, "_transport", None)
        if cached_transport is None:
            return

        close = getattr(cached_transport, "aclose", None)
        if close is not None:
            await cast(Any, close)()
        else:
            self._close_cached_transport()

        try:
            delattr(self, "_transport")
        except AttributeError:
            pass


class PlyntServiceMixin(_BasePlyntServiceMixin):
    """Build plynt transports and services inside DRF views

    Configure class attributes in a concrete APIView/ViewSet:

    1. ``settings_name``: Django settings attribute name.
    1. ``settings_class``: ``HTTPSettings`` subclass.
    1. Optionally ``cache_aliases`` and extra middleware.
    1. Optionally ``service_factories`` for named service factories.
    1. Optionally ``request_headers`` for inbound header propagation config.

    The mixin lazily builds and caches one transport per view instance.
    """

    middlewares: ClassVar[list[SyncMiddleware] | None] = None
    service_factories: ClassVar[dict[str, SyncServiceFactory] | None] = None

    def finalize_response(
        self,
        request: object,
        response: object,
        *args: object,
        **kwargs: object,
    ) -> Any:
        """Finalize the response and release the cached transport"""
        try:
            finalize_response = getattr(super(), "finalize_response", None)
            if finalize_response is not None:
                return cast(Any, finalize_response)(request, response, *args, **kwargs)
            return response
        finally:
            self._close_cached_transport()

    def get_transport(self) -> HttpxSyncTransport:
        """Return cached plynt transport for this view instance"""
        cached_transport = getattr(self, "_transport", None)
        if cached_transport is not None:
            return cast(HttpxSyncTransport, cached_transport)

        settings_name, settings_class = self._get_transport_settings()
        middlewares = list(self.middlewares or [])
        middleware_kwargs = self._get_request_header_builder_kwargs()
        if middleware_kwargs is not None:
            middlewares.insert(0, build_request_header_middleware(**middleware_kwargs))

        transport = transport_from_django_settings(
            settings_name,
            settings_class,
            settings_obj=self.get_django_settings_object(),
            response_cache_alias=self.cache_aliases.response,
            auth_cache_alias=self.cache_aliases.auth,
            middlewares=middlewares,
        )
        self._transport = transport
        return transport

    def get_request_header_middleware(self) -> SyncMiddleware | None:
        """Return middleware that propagates inbound request headers when enabled

        Header propagation is disabled by default and can be enabled by setting
        ``request_headers = RequestHeadersConfig(enabled=True)`` on the view.
        """
        middleware_kwargs = self._get_request_header_builder_kwargs()
        if middleware_kwargs is None:
            return None
        return build_request_header_middleware(**middleware_kwargs)

    def get_service_factories(self) -> dict[str, SyncServiceFactory]:
        """Return named service factories configured on this view"""
        return dict(self.service_factories or {})

    def get_service(self, name: str) -> Any:
        """Return one lazily-created named service instance"""
        cached_services = self._get_service_cache()

        if name in cached_services:
            return cached_services[name]

        factories = self.get_service_factories()
        if name not in factories:
            available = ", ".join(sorted(factories)) if factories else "none"
            raise KeyError(f"Unknown plynt service {name!r}; available: {available}")

        service = factories[name](self.get_transport())
        cached_services[name] = service
        return service

    def get_client(self, name: str = "client") -> Any:
        """Return named upstream client or service

        This is a convenience alias for ``get_service(...)``

        Args:
            name: Service key from ``service_factories``.
                Defaults to ``"client"``.

        """
        return self.get_service(name)


class AsyncPlyntServiceMixin(_BasePlyntServiceMixin):
    """Build async plynt transports and services inside DRF views

    This mixin is intended for async `APIView` handlers under ASGI. It mirrors
    `PlyntServiceMixin` but returns async transport and service instances.
    """

    middlewares: ClassVar[list[AsyncMiddleware] | None] = None
    service_factories: ClassVar[dict[str, AsyncServiceFactory] | None] = None

    def finalize_response(
        self,
        request: object,
        response: object,
        *args: object,
        **kwargs: object,
    ) -> Any:
        """Finalize the response and release the cached async transport"""
        try:
            finalize_response = getattr(super(), "finalize_response", None)
            if finalize_response is not None:
                return cast(Any, finalize_response)(request, response, *args, **kwargs)
            return response
        finally:
            close_transport_coro = self._aclose_cached_transport()
            try:
                asyncio.run(close_transport_coro)
            except RuntimeError as exc:
                if (
                    "asyncio.run() cannot be called from a running event loop"
                    not in str(exc)
                ):
                    close_transport_coro.close()
                    raise
                close_transport_coro.close()
                loop = asyncio.get_running_loop()
                cleanup_task = loop.create_task(self._aclose_cached_transport())
                _background_transport_cleanup_tasks.add(cleanup_task)
                cleanup_task.add_done_callback(
                    _background_transport_cleanup_tasks.discard
                )

    def get_transport(self) -> HttpxAsyncTransport:
        """Return cached async plynt transport for this view instance"""
        cached_transport = getattr(self, "_transport", None)
        if cached_transport is not None:
            return cast(HttpxAsyncTransport, cached_transport)

        settings_name, settings_class = self._get_transport_settings()
        middlewares = list(self.middlewares or [])
        middleware_kwargs = self._get_request_header_builder_kwargs()
        if middleware_kwargs is not None:
            middlewares.insert(
                0,
                build_async_request_header_middleware(**middleware_kwargs),
            )

        transport = async_transport_from_django_settings(
            settings_name,
            settings_class,
            settings_obj=self.get_django_settings_object(),
            response_cache_alias=self.cache_aliases.response,
            auth_cache_alias=self.cache_aliases.auth,
            middlewares=middlewares,
        )
        self._transport = transport
        return transport

    def get_request_header_middleware(self) -> AsyncMiddleware | None:
        """Return async middleware that propagates inbound request headers"""
        middleware_kwargs = self._get_request_header_builder_kwargs()
        if middleware_kwargs is None:
            return None
        return build_async_request_header_middleware(**middleware_kwargs)

    def get_service_factories(self) -> dict[str, AsyncServiceFactory]:
        """Return named async service factories configured on this view"""
        return dict(self.service_factories or {})

    def get_service(self, name: str) -> Any:
        """Return one lazily-created named async service instance"""
        cached_services = self._get_service_cache()

        if name in cached_services:
            return cached_services[name]

        factories = self.get_service_factories()
        if name not in factories:
            available = ", ".join(sorted(factories)) if factories else "none"
            raise KeyError(f"Unknown plynt service {name!r}; available: {available}")

        service = factories[name](self.get_transport())
        cached_services[name] = service
        return service

    def get_client(self, name: str = "client") -> Any:
        """Return named upstream async client or service

        This is a convenience alias for ``get_service(...)``

        Args:
            name: Service key from ``service_factories``.
                Defaults to ``"client"``.

        """
        return self.get_service(name)
