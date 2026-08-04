"""Shared test support for Salesforce auth middleware tests."""

from __future__ import annotations

from typing import Any, Literal, cast, overload

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from plynth.base.transport import AsyncTransport, SyncTransport
from plynth.connectors.salesforce.auth import (
    AsyncSalesforceClientCredentialsAuthMiddleware,
    AsyncSalesforceJWTBearerAuthMiddleware,
    AsyncSalesforcePasswordAuthMiddleware,
    SalesforceClientCredentialsAuthMiddleware,
    SalesforceJWTBearerAuthMiddleware,
    SalesforcePasswordAuthMiddleware,
)
from tests.connectors.salesforce.conftest import (
    DUMMY_CLIENT_ID,
    DUMMY_CLIENT_SECRET,
    DUMMY_PASSWORD,
    DUMMY_TOKEN_URL,
    DUMMY_USERNAME,
    FakeAsyncSalesforceTokenTransport,
    FakeSalesforceTokenTransport,
)


def inject_token_transport(
    auth: object,
    transport: SyncTransport | AsyncTransport,
) -> None:
    """Inject fake token transport to isolate middleware behavior in tests."""
    object.__setattr__(auth, "_transport", transport)


@overload
def make_auth(
    transport: SyncTransport | None = ...,
    *,
    flow: Literal["client_credentials"] = ...,
    async_mode: Literal[False] = ...,
    **kwargs: object,
) -> SalesforceClientCredentialsAuthMiddleware: ...


@overload
def make_auth(
    transport: SyncTransport | None = ...,
    *,
    flow: Literal["password"],
    async_mode: Literal[False] = ...,
    **kwargs: object,
) -> SalesforcePasswordAuthMiddleware: ...


@overload
def make_auth(
    transport: AsyncTransport | None = ...,
    *,
    flow: Literal["client_credentials"] = ...,
    async_mode: Literal[True],
    **kwargs: object,
) -> AsyncSalesforceClientCredentialsAuthMiddleware: ...


@overload
def make_auth(
    transport: AsyncTransport | None = ...,
    *,
    flow: Literal["password"],
    async_mode: Literal[True],
    **kwargs: object,
) -> AsyncSalesforcePasswordAuthMiddleware: ...


def make_auth(
    transport: SyncTransport | AsyncTransport | None = None,
    *,
    flow: str = "client_credentials",
    async_mode: bool = False,
    **kwargs: object,
) -> (
    SalesforceClientCredentialsAuthMiddleware
    | SalesforcePasswordAuthMiddleware
    | AsyncSalesforceClientCredentialsAuthMiddleware
    | AsyncSalesforcePasswordAuthMiddleware
):
    """Build Salesforce auth middleware wired to a deterministic test transport."""
    base: dict[str, object] = {
        "client_id": DUMMY_CLIENT_ID,
        "client_secret": DUMMY_CLIENT_SECRET,
        "token_url": DUMMY_TOKEN_URL,
    }
    if flow == "password":
        base.setdefault("username", DUMMY_USERNAME)
        base.setdefault("password", DUMMY_PASSWORD)

    constructor_kwargs = cast(dict[str, Any], {**base, **kwargs})
    auth: (
        SalesforceClientCredentialsAuthMiddleware
        | SalesforcePasswordAuthMiddleware
        | AsyncSalesforceClientCredentialsAuthMiddleware
        | AsyncSalesforcePasswordAuthMiddleware
    )
    if async_mode:
        if flow == "password":
            auth = AsyncSalesforcePasswordAuthMiddleware(**constructor_kwargs)
        else:
            auth = AsyncSalesforceClientCredentialsAuthMiddleware(**constructor_kwargs)
    else:
        if flow == "password":
            auth = SalesforcePasswordAuthMiddleware(**constructor_kwargs)
        else:
            auth = SalesforceClientCredentialsAuthMiddleware(**constructor_kwargs)

    injected_transport = transport or (
        FakeAsyncSalesforceTokenTransport()
        if async_mode
        else FakeSalesforceTokenTransport()
    )
    inject_token_transport(auth, injected_transport)
    return auth


def generate_rsa_private_key_pem() -> str:
    """Generate a throwaway RSA-2048 private key in PEM format."""
    key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend(),
    )
    return key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()


DUMMY_PRIVATE_KEY = generate_rsa_private_key_pem()
DUMMY_JWT_USERNAME = "integration@myorg.com"


@overload
def make_jwt_auth(
    transport: SyncTransport | None = ...,
    *,
    async_mode: Literal[False] = ...,
    **kwargs: object,
) -> SalesforceJWTBearerAuthMiddleware: ...


@overload
def make_jwt_auth(
    transport: AsyncTransport | None = ...,
    *,
    async_mode: Literal[True],
    **kwargs: object,
) -> AsyncSalesforceJWTBearerAuthMiddleware: ...


def make_jwt_auth(
    transport: SyncTransport | AsyncTransport | None = None,
    *,
    async_mode: bool = False,
    **kwargs: object,
) -> SalesforceJWTBearerAuthMiddleware | AsyncSalesforceJWTBearerAuthMiddleware:
    """Build JWT bearer auth middleware wired to deterministic test transport."""
    base: dict[str, object] = {
        "client_id": DUMMY_CLIENT_ID,
        "username": DUMMY_JWT_USERNAME,
        "private_key": DUMMY_PRIVATE_KEY,
        "token_url": DUMMY_TOKEN_URL,
    }
    constructor_kwargs = cast(dict[str, Any], {**base, **kwargs})
    if async_mode:
        auth_async = AsyncSalesforceJWTBearerAuthMiddleware(**constructor_kwargs)
        injected_async_transport = (
            transport
            if isinstance(transport, AsyncTransport)
            else FakeAsyncSalesforceTokenTransport()
        )
        inject_token_transport(auth_async, injected_async_transport)
        return auth_async

    auth_sync = SalesforceJWTBearerAuthMiddleware(**constructor_kwargs)
    injected_sync_transport = (
        transport
        if isinstance(transport, SyncTransport)
        else FakeSalesforceTokenTransport()
    )
    inject_token_transport(auth_sync, injected_sync_transport)
    return auth_sync
