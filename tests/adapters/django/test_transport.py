"""Tests for ``plynt.adapters.django.transport``."""

from __future__ import annotations

from collections.abc import Callable
from types import SimpleNamespace
from typing import cast

import pytest

import plynt.adapters.django.transport as django_transport
from plynt.adapters.django.transport import (
    async_transport_from_django_settings,
    transport_from_django_settings,
)
from plynt.base.middleware import AsyncMiddleware, NextAsyncHandler, SyncMiddleware
from plynt.base.request import Request
from plynt.base.response import Response
from plynt.http.auth import OAuth2ClientCredentialsConfig
from plynt.http.settings import HTTPSettings
from plynt.middleware.cache import AsyncCacheMiddleware, CacheMiddleware
from plynt.middleware.retry import AsyncRetryMiddleware, RetryMiddleware


class _DemoHTTPSettings(HTTPSettings):
    """Minimal HTTP settings model for transport helper tests."""

    client_id: str = ""
    client_secret: str = ""
    token_url: str = ""

    @property
    def auth(self) -> OAuth2ClientCredentialsConfig | None:
        """Return OAuth2 config only when credentials are present."""
        if not self.client_id or not self.client_secret or not self.token_url:
            return None
        return OAuth2ClientCredentialsConfig(
            client_id=self.client_id,
            client_secret=self.client_secret,
            token_url=self.token_url,
        )


class _DemoCustomMiddleware:
    """No-op middleware used to validate caller-supplied ordering."""

    def handle(
        self,
        request: Request,
        next_handler: Callable[[Request], Response],
    ) -> Response:
        """Pass request through without changes."""
        return next_handler(request)


class _CapturedTransport:
    """Capture constructor args passed by the transport helper."""

    def __init__(self, *, client: object, middlewares: list[object]) -> None:
        self.client = client
        self.middlewares = middlewares


class _CapturedAsyncTransport:
    """Capture constructor args passed by the async transport helper."""

    def __init__(self, *, client: object, middlewares: list[object]) -> None:
        self.client = client
        self.middlewares = middlewares


class _FakeDjangoCacheBackend:
    """Django cache backend stub used to validate alias wiring only."""

    def __init__(self, alias: str = "default") -> None:
        self.alias = alias


def _build_captured_transport(
    monkeypatch: pytest.MonkeyPatch,
    settings_obj: object,
    response_cache_alias: str | None = None,
    auth_cache_alias: str | None = None,
    middlewares: list[SyncMiddleware] | None = None,
) -> object:
    """Run helper with monkeypatched transport constructor and return capture."""
    captured_client = object()
    monkeypatch.setattr(django_transport, "HttpxSyncTransport", _CapturedTransport)
    monkeypatch.setattr(
        django_transport,
        "DjangoCacheBackend",
        _FakeDjangoCacheBackend,
    )
    monkeypatch.setattr(
        django_transport,
        "_build_httpx_client",
        lambda _: captured_client,
    )

    raw_transport: object = transport_from_django_settings(
        "SERVICE",
        _DemoHTTPSettings,
        settings_obj=settings_obj,
        response_cache_alias=response_cache_alias,
        auth_cache_alias=auth_cache_alias,
        middlewares=middlewares,
    )
    assert vars(raw_transport).get("client") is captured_client
    return raw_transport


def _build_captured_async_transport(
    monkeypatch: pytest.MonkeyPatch,
    settings_obj: object,
    response_cache_alias: str | None = None,
    auth_cache_alias: str | None = None,
    middlewares: list[AsyncMiddleware] | None = None,
) -> object:
    """Run async helper with monkeypatched transport constructor and return capture."""
    captured_client = object()
    monkeypatch.setattr(
        django_transport,
        "HttpxAsyncTransport",
        _CapturedAsyncTransport,
    )
    monkeypatch.setattr(
        django_transport,
        "DjangoCacheBackend",
        _FakeDjangoCacheBackend,
    )
    monkeypatch.setattr(
        django_transport,
        "_build_httpx_async_client",
        lambda _: captured_client,
    )

    raw_transport: object = async_transport_from_django_settings(
        "SERVICE",
        _DemoHTTPSettings,
        settings_obj=settings_obj,
        response_cache_alias=response_cache_alias,
        auth_cache_alias=auth_cache_alias,
        middlewares=middlewares,
    )
    assert vars(raw_transport).get("client") is captured_client
    return raw_transport


class TestTransportFromDjangoSettings:
    """Verify transport wiring behavior for Django settings integration."""

    def test_raises_type_error_for_non_http_settings_subclass(self) -> None:
        """Reject settings classes that do not inherit ``HTTPSettings``."""
        settings_obj = SimpleNamespace(SERVICE={})

        with pytest.raises(TypeError, match="HTTPSettings subclass"):
            transport_from_django_settings(
                "SERVICE",
                cast(type[HTTPSettings], object),
                settings_obj=settings_obj,
            )

    def test_builds_retry_only_transport_without_optional_aliases(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Wire retry middleware by default when no auth/cache alias is set."""
        settings_obj = SimpleNamespace(
            SERVICE={
                "BASE_URL": "https://api.example.test",
                "MAX_ATTEMPTS": 4,
            }
        )

        transport = _build_captured_transport(
            monkeypatch,
            settings_obj,
        )
        middlewares = cast(list[object], vars(transport)["middlewares"])

        assert len(middlewares) == 1
        assert isinstance(middlewares[0], RetryMiddleware)

    def test_wires_django_response_cache_alias(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Attach ``CacheMiddleware`` with ``DjangoCacheBackend`` alias."""
        settings_obj = SimpleNamespace(
            SERVICE={
                "BASE_URL": "https://api.example.test",
            }
        )

        transport = _build_captured_transport(
            monkeypatch,
            settings_obj,
            response_cache_alias="api_cache",
        )
        middlewares = cast(list[object], vars(transport)["middlewares"])

        cache_middleware = next(
            mw for mw in middlewares if isinstance(mw, CacheMiddleware)
        )
        cache_backend = vars(cache_middleware)["_backend"]
        assert isinstance(cache_backend, _FakeDjangoCacheBackend)
        assert cache_backend.alias == "api_cache"

    def test_wires_oauth_token_cache_alias(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Attach Django-backed token cache to OAuth middleware."""
        settings_obj = SimpleNamespace(
            SERVICE={
                "BASE_URL": "https://api.example.test",
                "CLIENT_ID": "client-id",
                "CLIENT_SECRET": "client-secret",
                "TOKEN_URL": "https://auth.example.test/token",
            }
        )

        transport = _build_captured_transport(
            monkeypatch,
            settings_obj,
            auth_cache_alias="oauth_cache",
        )
        middlewares = cast(list[object], vars(transport)["middlewares"])

        auth_middleware = middlewares[0]
        auth_cache = vars(auth_middleware).get("_cache")
        assert isinstance(auth_cache, _FakeDjangoCacheBackend)
        assert auth_cache.alias == "oauth_cache"

    def test_prepends_caller_supplied_middlewares(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Keep user-provided middleware at the front of the chain."""
        settings_obj = SimpleNamespace(
            SERVICE={
                "BASE_URL": "https://api.example.test",
            }
        )
        custom = _DemoCustomMiddleware()

        transport = _build_captured_transport(
            monkeypatch,
            settings_obj,
            middlewares=[custom],
        )
        middlewares = cast(list[object], vars(transport)["middlewares"])

        assert middlewares[0] is custom


class _DemoAsyncCustomMiddleware:
    """No-op async middleware used to validate caller-supplied ordering."""

    async def handle(
        self,
        request: Request,
        next_handler: NextAsyncHandler,
    ) -> Response:
        """Pass request through without changes."""
        return await next_handler(request)


class TestAsyncTransportFromDjangoSettings:
    """Verify async transport wiring behavior for Django settings integration."""

    def test_raises_type_error_for_non_http_settings_subclass(self) -> None:
        """Reject settings classes that do not inherit ``HTTPSettings``."""
        settings_obj = SimpleNamespace(SERVICE={})

        with pytest.raises(TypeError, match="HTTPSettings subclass"):
            async_transport_from_django_settings(
                "SERVICE",
                cast(type[HTTPSettings], object),
                settings_obj=settings_obj,
            )

    def test_builds_retry_only_transport_without_optional_aliases(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Wire async retry middleware by default when no auth/cache alias is set."""
        settings_obj = SimpleNamespace(
            SERVICE={
                "BASE_URL": "https://api.example.test",
                "MAX_ATTEMPTS": 4,
            }
        )

        transport = _build_captured_async_transport(
            monkeypatch,
            settings_obj,
        )
        middlewares = cast(list[object], vars(transport)["middlewares"])

        assert len(middlewares) == 1
        assert isinstance(middlewares[0], AsyncRetryMiddleware)

    def test_wires_django_response_cache_alias(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Attach ``AsyncCacheMiddleware`` with ``DjangoCacheBackend`` alias."""
        settings_obj = SimpleNamespace(
            SERVICE={
                "BASE_URL": "https://api.example.test",
            }
        )

        transport = _build_captured_async_transport(
            monkeypatch,
            settings_obj,
            response_cache_alias="api_cache",
        )
        middlewares = cast(list[object], vars(transport)["middlewares"])

        cache_middleware = next(
            mw for mw in middlewares if isinstance(mw, AsyncCacheMiddleware)
        )
        cache_backend = vars(cache_middleware)["_backend"]
        assert isinstance(cache_backend, _FakeDjangoCacheBackend)
        assert cache_backend.alias == "api_cache"

    def test_wires_oauth_token_cache_alias(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Attach Django-backed token cache to async OAuth middleware."""
        settings_obj = SimpleNamespace(
            SERVICE={
                "BASE_URL": "https://api.example.test",
                "CLIENT_ID": "client-id",
                "CLIENT_SECRET": "client-secret",
                "TOKEN_URL": "https://auth.example.test/token",
            }
        )

        transport = _build_captured_async_transport(
            monkeypatch,
            settings_obj,
            auth_cache_alias="oauth_cache",
        )
        middlewares = cast(list[object], vars(transport)["middlewares"])

        auth_middleware = middlewares[0]
        auth_cache = vars(auth_middleware).get("_cache")
        assert isinstance(auth_cache, _FakeDjangoCacheBackend)
        assert auth_cache.alias == "oauth_cache"

    def test_prepends_caller_supplied_middlewares(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Keep user-provided async middleware at the front of the chain."""
        settings_obj = SimpleNamespace(
            SERVICE={
                "BASE_URL": "https://api.example.test",
            }
        )
        custom = _DemoAsyncCustomMiddleware()

        transport = _build_captured_async_transport(
            monkeypatch,
            settings_obj,
            middlewares=[custom],
        )
        middlewares = cast(list[object], vars(transport)["middlewares"])

        assert middlewares[0] is custom
