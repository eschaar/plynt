# Plynth

Plynth is a modular, framework-agnostic Python library for building external
API clients and services.

Plynth focuses on a stable integration foundation:

- framework-agnostic design
- sync and async support from one codebase
- explicit configuration and minimal hidden behavior
- typed settings and reusable middleware patterns

## Installation

Requires **Python 3.11 or later**.

```bash
pip install plynth
```

Optional extras:

```bash
pip install "plynth[httpx]"       # httpx transport
pip install "plynth[salesforce]"  # Salesforce REST connector
```

## Salesforce connector

`plynth[salesforce]` ships a ready-to-use Salesforce REST API integration
with typed SOQL queries, OAuth2 auth flows, and sync/async support:

```python
from plynth.connectors.salesforce.auth import SalesforceClientCredentialsAuthMiddleware
from plynth.connectors.salesforce.client import SalesforceAPIClient
from plynth.connectors.salesforce.facade import SalesforceAPIFacade
from plynth.http.transport import HttpxSyncTransport

auth = SalesforceClientCredentialsAuthMiddleware(
    client_id="...",
    client_secret="...",
    token_url="https://login.salesforce.com/services/oauth2/token",
)
transport = HttpxSyncTransport(middlewares=[auth])
client = SalesforceAPIClient(auth=auth, transport=transport)
sf = SalesforceAPIFacade(client)

result = sf.query().query("SELECT Id, Name FROM Account LIMIT 5")
for record in result.records:
    print(record["Name"])
```

See the [Salesforce connector docs](https://github.com/eschaar/plynth/tree/main/docs/connectors/salesforce)
for the full guide including JWT Bearer auth, pagination, bulk ingest, and more.

## Project Status

Current public release line:

- `0.1.0`: clean core foundation
- `0.2.0`: Salesforce connector baseline
- `0.2.1`: patch release

## Documentation

- [README](https://github.com/eschaar/plynth/blob/main/README.md)
- [Changelog](https://github.com/eschaar/plynth/blob/main/CHANGELOG.md)
- [Architecture ADRs](https://github.com/eschaar/plynth/tree/main/docs/architecture/adr)
- [Salesforce connector docs](https://github.com/eschaar/plynth/tree/main/docs/connectors/salesforce)

## License

MIT
