"""Shared Salesforce integration test fixtures."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeAlias

import pytest

from plynt.base.request import Request
from plynt.base.response import Response
from plynt.base.transport import AsyncTransport, SyncTransport
from plynt.connectors.salesforce.auth import (
    AsyncSalesforceClientCredentialsAuthMiddleware,
    AsyncSalesforcePasswordAuthMiddleware,
    SalesforceClientCredentialsAuthMiddleware,
    SalesforcePasswordAuthMiddleware,
)
from plynt.http.renderer import JSONRenderer

DUMMY_CLIENT_ID = "sf-client-id"
DUMMY_CLIENT_SECRET = "sf-client-secret"
DUMMY_TOKEN_URL = "https://login.salesforce.com/services/oauth2/token"
DUMMY_ACCESS_TOKEN = "sf-access-token"
DUMMY_INSTANCE_URL = "https://myorg.my.salesforce.com"
DUMMY_USERNAME = "john.doe@example.com"
DUMMY_PASSWORD = "secret-password"

_JSON_RENDERER = JSONRenderer()


def render_json_bytes(data: Any) -> bytes:
    """Render Python data to JSON bytes used by transport stubs in tests."""
    return _JSON_RENDERER.render(data)


# Backward-compatible alias used by existing tests.
_json_bytes = render_json_bytes


SyncSalesforceAuthMiddleware: TypeAlias = (
    SalesforceClientCredentialsAuthMiddleware | SalesforcePasswordAuthMiddleware
)

AsyncSalesforceAuthMiddleware: TypeAlias = (
    AsyncSalesforceClientCredentialsAuthMiddleware
    | AsyncSalesforcePasswordAuthMiddleware
)


class FakeSalesforceTokenTransport(SyncTransport):
    """Simulates a Salesforce token endpoint response including instance_url."""

    def __init__(
        self,
        token: str = DUMMY_ACCESS_TOKEN,
        instance_url: str = DUMMY_INSTANCE_URL,
        expires_in: int = 3600,
        status: int = 200,
        include_instance_url: bool = True,
    ) -> None:
        """Initialize a sync token-transport stub with configurable payload."""
        body: dict[str, object] = {
            "access_token": token,
            "expires_in": expires_in,
        }
        if include_instance_url:
            body["instance_url"] = instance_url
        self._body = render_json_bytes(body)
        self._status = status
        self.calls: int = 0
        self.last_request: Request | None = None

    def send(self, request: Request) -> Response:
        """Return a token response and capture call metadata for assertions."""
        self.calls += 1
        self.last_request = request
        return Response(status_code=self._status, content=self._body)


class FakeAsyncSalesforceTokenTransport(AsyncTransport):
    """Async transport stub for Salesforce token endpoint responses."""

    def __init__(
        self,
        token: str = DUMMY_ACCESS_TOKEN,
        instance_url: str = DUMMY_INSTANCE_URL,
        expires_in: int = 3600,
        status: int = 200,
        include_instance_url: bool = True,
    ) -> None:
        """Initialize an async token-transport stub with configurable payload."""
        body: dict[str, object] = {
            "access_token": token,
            "expires_in": expires_in,
        }
        if include_instance_url:
            body["instance_url"] = instance_url
        self._body = render_json_bytes(body)
        self._status = status
        self.calls: int = 0
        self.last_request: Request | None = None

    async def send(self, request: Request) -> Response:
        """Return a token response and capture call metadata for assertions."""
        self.calls += 1
        self.last_request = request
        return Response(status_code=self._status, content=self._body)


def _auth_base_kwargs(*, include_password: bool = False) -> dict[str, str]:
    """Build shared Salesforce auth kwargs used by sync and async factories."""
    kwargs = {
        "client_id": DUMMY_CLIENT_ID,
        "client_secret": DUMMY_CLIENT_SECRET,
        "token_url": DUMMY_TOKEN_URL,
    }
    if include_password:
        kwargs["username"] = DUMMY_USERNAME
        kwargs["password"] = DUMMY_PASSWORD
    return kwargs


def _new_sync_salesforce_auth(
    token_transport: SyncTransport | None = None,
    *,
    auth_cls: type[SyncSalesforceAuthMiddleware] = (
        SalesforceClientCredentialsAuthMiddleware
    ),
    **kwargs: object,
) -> SyncSalesforceAuthMiddleware:
    """Create a sync Salesforce auth middleware with optional overrides."""
    base_kwargs = _auth_base_kwargs(
        include_password=auth_cls is SalesforcePasswordAuthMiddleware,
    )
    auth = auth_cls(**{**base_kwargs, **kwargs})  # type: ignore[arg-type]
    auth._transport = token_transport or FakeSalesforceTokenTransport()
    return auth


def _new_async_salesforce_auth(
    token_transport: AsyncTransport | None = None,
    *,
    auth_cls: type[AsyncSalesforceAuthMiddleware] = (
        AsyncSalesforceClientCredentialsAuthMiddleware
    ),
    **kwargs: object,
) -> AsyncSalesforceAuthMiddleware:
    """Create an async Salesforce auth middleware with optional overrides."""
    base_kwargs = _auth_base_kwargs(
        include_password=auth_cls is AsyncSalesforcePasswordAuthMiddleware,
    )
    auth = auth_cls(**{**base_kwargs, **kwargs})  # type: ignore[arg-type]
    auth._transport = token_transport or FakeAsyncSalesforceTokenTransport()
    return auth


SyncAuthFactory: TypeAlias = Callable[..., SyncSalesforceAuthMiddleware]

AsyncAuthFactory: TypeAlias = Callable[..., AsyncSalesforceAuthMiddleware]

SyncTokenTransportFactory: TypeAlias = Callable[..., FakeSalesforceTokenTransport]

AsyncTokenTransportFactory: TypeAlias = Callable[
    ...,
    FakeAsyncSalesforceTokenTransport,
]


@pytest.fixture
def make_sync_salesforce_token_transport() -> SyncTokenTransportFactory:
    """Factory fixture for sync Salesforce token transport stubs."""
    return FakeSalesforceTokenTransport


@pytest.fixture(scope="session")
def salesforce_base_url() -> str:
    """Return a shared Salesforce base URL used in connector test clients."""
    return DUMMY_INSTANCE_URL


@pytest.fixture
def make_async_salesforce_token_transport() -> AsyncTokenTransportFactory:
    """Factory fixture for async Salesforce token transport stubs."""
    return FakeAsyncSalesforceTokenTransport


@pytest.fixture
def make_sync_salesforce_auth() -> SyncAuthFactory:
    """Factory fixture for constructing sync Salesforce auth middlewares."""
    return _new_sync_salesforce_auth


@pytest.fixture
def make_async_salesforce_auth() -> AsyncAuthFactory:
    """Factory fixture for constructing async Salesforce auth middlewares."""
    return _new_async_salesforce_auth
