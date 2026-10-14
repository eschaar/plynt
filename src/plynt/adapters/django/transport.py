"""Django transport helpers for Plynt.

Builds sync and async plynt transports from a named Django settings block and
optional Django cache aliases.
"""

from __future__ import annotations

from typing import TypeVar

from plynt.adapters.django.cache import DjangoCacheBackend
from plynt.adapters.django.settings import from_django_settings
from plynt.base.middleware import AsyncMiddleware, SyncMiddleware
from plynt.http.auth import async_auth_from_config, auth_from_config
from plynt.http.policies import HttpRetryPolicy
from plynt.http.settings import HTTPSettings
from plynt.http.transport import (
    HttpxAsyncTransport,
    HttpxSyncTransport,
    _build_httpx_async_client,
    _build_httpx_client,
)
from plynt.middleware.cache import AsyncCacheMiddleware, CacheMiddleware
from plynt.middleware.retry import AsyncRetryMiddleware, RetryMiddleware

__all__ = [
    "async_transport_from_django_settings",
    "transport_from_django_settings",
]

SettingsT = TypeVar("SettingsT", bound=HTTPSettings)


def transport_from_django_settings(
    name: str,
    settings_class: type[SettingsT],
    *,
    settings_obj: object | None = None,
    response_cache_alias: str | None = None,
    auth_cache_alias: str | None = None,
    middlewares: list[SyncMiddleware] | None = None,
) -> HttpxSyncTransport:
    """Build a sync transport from one Django settings mapping.

    Args:
        name: Attribute name on the Django settings object.
        settings_class: ``HTTPSettings`` subclass used to parse the mapping.
        settings_obj: Optional settings-like object used instead of
            ``django.conf.settings``.
        response_cache_alias: Optional Django cache alias used for response
            caching middleware.
        auth_cache_alias: Optional Django cache alias used as OAuth2 token
            cache for auth middleware.
        middlewares: Optional preconfigured middleware list to prepend.

    Returns:
        Fully configured sync transport with auth/cache/retry wiring.

    """
    if not issubclass(settings_class, HTTPSettings):
        raise TypeError("settings_class must be an HTTPSettings subclass")

    settings = from_django_settings(
        name,
        settings_class,
        settings_obj=settings_obj,
    )

    resolved_middlewares: list[SyncMiddleware] = list(middlewares or [])

    auth_config = settings.auth
    if auth_config is not None:
        auth_token_cache = (
            DjangoCacheBackend(alias=auth_cache_alias)
            if auth_cache_alias is not None
            else None
        )
        resolved_middlewares.append(
            auth_from_config(auth_config, token_cache=auth_token_cache)
        )

    if response_cache_alias is not None:
        resolved_middlewares.append(
            CacheMiddleware(DjangoCacheBackend(alias=response_cache_alias))
        )

    retry_policy = settings.retry or HttpRetryPolicy(max_attempts=settings.max_attempts)
    resolved_middlewares.append(RetryMiddleware(retry_policy))

    return HttpxSyncTransport(
        client=_build_httpx_client(settings),
        middlewares=resolved_middlewares,
    )


def async_transport_from_django_settings(
    name: str,
    settings_class: type[SettingsT],
    *,
    settings_obj: object | None = None,
    response_cache_alias: str | None = None,
    auth_cache_alias: str | None = None,
    middlewares: list[AsyncMiddleware] | None = None,
) -> HttpxAsyncTransport:
    """Build an async transport from one Django settings mapping.

    Args:
        name: Attribute name on the Django settings object.
        settings_class: ``HTTPSettings`` subclass used to parse the mapping.
        settings_obj: Optional settings-like object used instead of
            ``django.conf.settings``.
        response_cache_alias: Optional Django cache alias used for response
            caching middleware.
        auth_cache_alias: Optional Django cache alias used as OAuth2 token
            cache for auth middleware.
        middlewares: Optional preconfigured async middleware list to prepend.

    Returns:
        Fully configured async transport with auth/cache/retry wiring.

    """
    if not issubclass(settings_class, HTTPSettings):
        raise TypeError("settings_class must be an HTTPSettings subclass")

    settings = from_django_settings(
        name,
        settings_class,
        settings_obj=settings_obj,
    )

    resolved_middlewares: list[AsyncMiddleware] = list(middlewares or [])

    auth_config = settings.auth
    if auth_config is not None:
        auth_token_cache = (
            DjangoCacheBackend(alias=auth_cache_alias)
            if auth_cache_alias is not None
            else None
        )
        resolved_middlewares.append(
            async_auth_from_config(auth_config, token_cache=auth_token_cache)
        )

    if response_cache_alias is not None:
        resolved_middlewares.append(
            AsyncCacheMiddleware(DjangoCacheBackend(alias=response_cache_alias))
        )

    retry_policy = settings.retry or HttpRetryPolicy(max_attempts=settings.max_attempts)
    resolved_middlewares.append(AsyncRetryMiddleware(retry_policy))

    return HttpxAsyncTransport(
        client=_build_httpx_async_client(settings),
        middlewares=resolved_middlewares,
    )
