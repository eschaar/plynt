# Salesforce Client Credentials example

Use this snippet as a copy-paste starting point for a complete sync workflow
using OAuth2 Client Credentials (machine-to-machine).

Required variables (see `example.env`):

- `SF_CLIENT_ID`
- `SF_CLIENT_SECRET`
- `SF_TOKEN_URL`
- `SF_API_VERSION` (optional)

```python
from __future__ import annotations

import sys
from pathlib import Path

from _demo import run_demo
from pydantic_settings import SettingsConfigDict

from plynt.connectors.salesforce.auth import (
    SalesforceClientCredentialsAuthMiddleware,
)
from plynt.connectors.salesforce.client import SalesforceAPIClient
from plynt.connectors.salesforce.facade import SalesforceAPIFacade
from plynt.connectors.salesforce.settings import SalesforceSettings
from plynt.http.transport import HttpxSyncTransport


class _Settings(SalesforceSettings):
    model_config = SettingsConfigDict(
        env_prefix="SF_",
        env_file=str(Path(__file__).parent / ".env"),
        env_file_encoding="utf-8",
    )

    demo_search_term: str = "Inc"


def main() -> None:
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
```
