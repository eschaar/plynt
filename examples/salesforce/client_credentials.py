"""Salesforce quickstart — OAuth2 Client Credentials flow.

Demonstrates a complete sync workflow using the Plynth Salesforce integration
with the OAuth2 Client Credentials (machine-to-machine) grant type.

Copy ``example.env`` to ``.env`` in this same directory and fill in your
values before running::

    cp examples/salesforce/example.env examples/salesforce/.env
    python examples/salesforce/client_credentials.py

Required variables (see ``example.env``)::

    SF_CLIENT_ID
    SF_CLIENT_SECRET
    SF_TOKEN_URL
    SF_API_VERSION   (optional)

"""

from __future__ import annotations

import sys
from pathlib import Path

from _demo import run_demo
from pydantic_settings import SettingsConfigDict

from plynth.connectors.salesforce.settings import SalesforceSettings


class _Settings(SalesforceSettings):
    model_config = SettingsConfigDict(
        env_prefix="SF_",
        env_file=str(Path(__file__).parent / ".env"),
        env_file_encoding="utf-8",
    )

    demo_search_term: str = "Inc"


def main() -> None:
    from plynth.connectors.salesforce.auth import (
        SalesforceClientCredentialsAuthMiddleware,
    )
    from plynth.connectors.salesforce.client import SalesforceAPIClient
    from plynth.connectors.salesforce.facade import SalesforceAPIFacade
    from plynth.http.transport import HttpxSyncTransport

    settings = _Settings()
    if not settings.client_id or not settings.client_secret or not settings.token_url:
        print(
            "ERROR: SF_CLIENT_ID, SF_CLIENT_SECRET and SF_TOKEN_URL must be set.",
            file=sys.stderr,
        )
        print(
            "       Copy examples/salesforce/example.env to "
            "examples/salesforce/.env and fill it in.",
            file=sys.stderr,
        )
        sys.exit(1)

    auth = SalesforceClientCredentialsAuthMiddleware(
        client_id=settings.client_id,
        client_secret=settings.client_secret,
        token_url=settings.token_url,
    )
    transport = HttpxSyncTransport(middlewares=[auth])
    client = SalesforceAPIClient(auth=auth, transport=transport)
    run_demo(
        SalesforceAPIFacade(client), settings, search_term=settings.demo_search_term
    )


if __name__ == "__main__":
    main()
