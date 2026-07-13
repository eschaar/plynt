# Salesforce Username/Password example

Use this snippet as a copy-paste starting point for OAuth2 Resource Owner
Password Credentials (ROPC), with both sync and async flows.

Required variables (see `example.env`):

- `SF_CLIENT_ID`
- `SF_CLIENT_SECRET`
- `SF_TOKEN_URL`
- `SF_USERNAME`
- `SF_PASSWORD`
- `SF_SECURITY_TOKEN` (optional, appended when set)
- `SF_API_VERSION` (optional)

```python
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
```
