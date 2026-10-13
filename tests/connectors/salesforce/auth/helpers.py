"""Shared helpers for Salesforce auth middleware tests."""

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
def make_oauth_auth(
    transport: SyncTransport | None = ...,
    *,
    flow: Literal["client_credentials"] = ...,
    async_mode: Literal[False] = ...,
    **kwargs: object,
) -> SalesforceClientCredentialsAuthMiddleware: ...


@overload
def make_oauth_auth(
    transport: SyncTransport | None = ...,
    *,
    flow: Literal["password"],
    async_mode: Literal[False] = ...,
    **kwargs: object,
) -> SalesforcePasswordAuthMiddleware: ...


@overload
def make_oauth_auth(
    transport: AsyncTransport | None = ...,
    *,
    flow: Literal["client_credentials"] = ...,
    async_mode: Literal[True],
    **kwargs: object,
) -> AsyncSalesforceClientCredentialsAuthMiddleware: ...


@overload
def make_oauth_auth(
    transport: AsyncTransport | None = ...,
    *,
    flow: Literal["password"],
    async_mode: Literal[True],
    **kwargs: object,
) -> AsyncSalesforcePasswordAuthMiddleware: ...


def make_oauth_auth(
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
    extra_kwargs = cast(dict[str, Any], dict(kwargs))
    client_id = cast(str, extra_kwargs.pop("client_id", DUMMY_CLIENT_ID))
    client_secret = cast(
        str,
        extra_kwargs.pop("client_secret", DUMMY_CLIENT_SECRET),
    )
    token_url = cast(str, extra_kwargs.pop("token_url", DUMMY_TOKEN_URL))

    auth: (
        SalesforceClientCredentialsAuthMiddleware
        | SalesforcePasswordAuthMiddleware
        | AsyncSalesforceClientCredentialsAuthMiddleware
        | AsyncSalesforcePasswordAuthMiddleware
    )
    if async_mode:
        if flow == "password":
            username = cast(str, extra_kwargs.pop("username", DUMMY_USERNAME))
            password = cast(str, extra_kwargs.pop("password", DUMMY_PASSWORD))
            auth = AsyncSalesforcePasswordAuthMiddleware(
                client_id=client_id,
                client_secret=client_secret,
                token_url=token_url,
                username=username,
                password=password,
                **extra_kwargs,
            )
        else:
            auth = AsyncSalesforceClientCredentialsAuthMiddleware(
                client_id=client_id,
                client_secret=client_secret,
                token_url=token_url,
                **extra_kwargs,
            )
    else:
        if flow == "password":
            username = cast(str, extra_kwargs.pop("username", DUMMY_USERNAME))
            password = cast(str, extra_kwargs.pop("password", DUMMY_PASSWORD))
            auth = SalesforcePasswordAuthMiddleware(
                client_id=client_id,
                client_secret=client_secret,
                token_url=token_url,
                username=username,
                password=password,
                **extra_kwargs,
            )
        else:
            auth = SalesforceClientCredentialsAuthMiddleware(
                client_id=client_id,
                client_secret=client_secret,
                token_url=token_url,
                **extra_kwargs,
            )

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
def make_bearer_auth(
    transport: SyncTransport | None = ...,
    *,
    async_mode: Literal[False] = ...,
    **kwargs: object,
) -> SalesforceJWTBearerAuthMiddleware: ...


@overload
def make_bearer_auth(
    transport: AsyncTransport | None = ...,
    *,
    async_mode: Literal[True],
    **kwargs: object,
) -> AsyncSalesforceJWTBearerAuthMiddleware: ...


def make_bearer_auth(
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
