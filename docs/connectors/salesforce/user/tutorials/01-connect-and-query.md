# Connect and run your first Salesforce query

This tutorial takes you from zero to a working Salesforce query in Python.
You will set up a Connected App, configure credentials, build a client, and
retrieve Account records.

## Prerequisites

- Python 3.12 or later
- A Salesforce org (Developer Edition is free)
- Admin access to set up a Connected App

## Step 1 — Create a Connected App

In Salesforce Setup:

1. Go to **App Manager → New Connected App**.
1. Enable **OAuth Settings**.
1. Add the scope **Manage user data via APIs (api)**.
1. Enable **Client Credentials Flow** under OAuth policies.
1. Note your `Consumer Key` (client ID) and `Consumer Secret`.

## Step 2 — Install Plynt

```bash
pip install "plynt[salesforce]"
```

## Step 3 — Create a `.env` file

```ini
SF_CLIENT_ID=3MVG9...
SF_CLIENT_SECRET=abc123
SF_TOKEN_URL=https://login.salesforce.com/services/oauth2/token
SF_API_VERSION=62.0
```

Add `.env` to `.gitignore`. Never commit credentials.

## Step 4 — Load settings

```python
from pydantic_settings import SettingsConfigDict
from plynt.connectors.salesforce.settings import SalesforceSettings


class MySettings(SalesforceSettings):
    model_config = SettingsConfigDict(env_prefix="SF_", env_file=".env")


settings = MySettings()
```

## Step 5 — Build the client

```python
from plynt.connectors.salesforce.auth import SalesforceClientCredentialsAuthMiddleware
from plynt.connectors.salesforce.client import SalesforceAPIClient
from plynt.connectors.salesforce.facade import SalesforceAPIFacade
from plynt.http.transport import HttpxSyncTransport

auth = SalesforceClientCredentialsAuthMiddleware(
    client_id=settings.client_id,
    client_secret=settings.client_secret,
    token_url=settings.token_url,
)
transport = HttpxSyncTransport(middlewares=[auth])
client = SalesforceAPIClient(auth=auth, transport=transport)
sf = SalesforceAPIFacade(client)
```

`SalesforceClientCredentialsAuthMiddleware` fetches a token on the first
request and automatically refreshes it when it expires. The `instance_url`
is resolved from the token response — you do not need to set it manually.

## Step 6 — Run a query

```python
result = sf.query().query("SELECT Id, Name, Industry FROM Account LIMIT 10")

print(f"Total records: {result.total_size}")
for record in result.records:
    print(f"  {record['Id']}  {record['Name']}  ({record.get('Industry', '—')})")
```

## Step 7 — Paginate through all results

When a query returns more records than the page size, use `query_all`:

```python
all_records = sf.query().query_all("SELECT Id, Name FROM Account")
print(f"Fetched {len(all_records.records)} of {all_records.total_size} accounts")
```

`query_all` follows `nextRecordsUrl` automatically across all pages and
returns a `SalesforceQueryResponse` with `done=True` and all records in
`records`.

## What you built

- Typed settings loaded from environment variables
- An OAuth2 Client Credentials auth middleware that handles token lifecycle
- A `SalesforceAPIFacade` giving access to all connector services
- A SOQL query with typed response and automatic pagination

## Next steps

- [How to authenticate with different flows](../how-to/authenticate.md)
- [How to work with SObject records](../how-to/sobject-crud.md)
- [How to handle errors](../how-to/handle-errors.md)
