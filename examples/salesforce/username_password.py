"""Salesforce quickstart — OAuth2 Username/Password (ROPC) flow.

Demonstrates both sync and async workflows using the Plynth Salesforce
integration with the OAuth2 Resource Owner Password Credentials (ROPC)
grant type. Debug logging is enabled so you can see the auth/transport
activity (token fetch, cache hit/miss, requests) in the console.

Use this flow when you are running server-side automation under a named
Salesforce user and cannot use Client Credentials.

.. warning::
    The ROPC flow is considered legacy. Prefer Client Credentials for
    machine-to-machine integrations wherever supported.

Copy ``example.env`` to ``.env`` in this same directory and fill in your
values before running::

    cp examples/salesforce/example.env examples/salesforce/.env
    python examples/salesforce/username_password.py

Required variables (see ``example.env``)::

    SF_CLIENT_ID
    SF_CLIENT_SECRET
    SF_TOKEN_URL
    SF_USERNAME
    SF_PASSWORD
    SF_SECURITY_TOKEN   (optional — appended to password when set)
    SF_API_VERSION      (optional)

"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from _demo import configure_logging, run_async_demo, run_demo
from pydantic_settings import SettingsConfigDict

from plynth.connectors.salesforce.auth import (
    AsyncSalesforcePasswordAuthMiddleware,
    SalesforcePasswordAuthMiddleware,
)
from plynth.connectors.salesforce.client import (
    AsyncSalesforceAPIClient,
    SalesforceAPIClient,
)
from plynth.connectors.salesforce.facade import (
    AsyncSalesforceAPIFacade,
    SalesforceAPIFacade,
)
from plynth.connectors.salesforce.settings import SalesforceSettings
from plynth.http.transport import HttpxAsyncTransport, HttpxSyncTransport
from plynth.middleware.logging import AsyncLoggingMiddleware, LoggingMiddleware


class _Settings(SalesforceSettings):
    model_config = SettingsConfigDict(
        env_prefix="SF_",
        env_file=str(Path(__file__).parent / ".env"),
        env_file_encoding="utf-8",
    )

    demo_search_term: str = "Inc"


def _check_settings(settings: SalesforceSettings) -> None:
    """Exit with a clear error when required env vars are missing."""
    missing = [
        var
        for var, val in [
            ("SF_CLIENT_ID", settings.client_id),
            ("SF_CLIENT_SECRET", settings.client_secret),
            ("SF_TOKEN_URL", settings.token_url),
            ("SF_USERNAME", settings.username),
            ("SF_PASSWORD", settings.password),
        ]
        if not val
    ]
    if missing:
        print(f"ERROR: {', '.join(missing)} must be set.", file=sys.stderr)
        print(
            "       Copy examples/salesforce/example.env to "
            "examples/salesforce/.env and fill it in.",
            file=sys.stderr,
        )
        sys.exit(1)


def main_sync(settings: _Settings) -> None:
    """Run the synchronous username/password Salesforce demo."""
    auth = SalesforcePasswordAuthMiddleware(
        client_id=settings.client_id,
        client_secret=settings.client_secret,
        token_url=settings.token_url,
        username=settings.username,
        password=settings.password,
        security_token=settings.security_token,
    )
    transport = HttpxSyncTransport(middlewares=[LoggingMiddleware(), auth])
    client = SalesforceAPIClient(auth=auth, transport=transport)
    run_demo(
        SalesforceAPIFacade(client), settings, search_term=settings.demo_search_term
    )


async def main_async(settings: _Settings) -> None:
    """Run the asynchronous username/password Salesforce demo."""
    auth = AsyncSalesforcePasswordAuthMiddleware(
        client_id=settings.client_id,
        client_secret=settings.client_secret,
        token_url=settings.token_url,
        username=settings.username,
        password=settings.password,
        security_token=settings.security_token,
    )
    transport = HttpxAsyncTransport(middlewares=[AsyncLoggingMiddleware(), auth])
    client = AsyncSalesforceAPIClient(auth=auth, transport=transport)
    await run_async_demo(
        AsyncSalesforceAPIFacade(client),
        settings,
        search_term=settings.demo_search_term,
    )


if __name__ == "__main__":
    configure_logging()
    _settings = _Settings()
    _check_settings(_settings)

    print("\n" + "#" * 60)
    print("# SYNC")
    print("#" * 60)
    main_sync(_settings)

    print("\n" + "#" * 60)
    print("# ASYNC")
    print("#" * 60)
    asyncio.run(main_async(_settings))
