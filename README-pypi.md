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
pip install "plynth[httpx]"       # httpx2 transport
pip install "plynth[salesforce]"  # Salesforce REST connector
```

### Canonical extras matrix

| Extra        | Installs                                | Typical use                                       |
| ------------ | --------------------------------------- | ------------------------------------------------- |
| `httpx`      | `httpx2` transport backend              | Core HTTP transport for sync and async clients    |
| `django`     | Django adapter support + `httpx2`       | Django integration helpers and cache adapters     |
| `drf`        | DRF adapter support + Django + `httpx2` | DRF service mixins and exception mapping patterns |
| `fastapi`    | FastAPI adapter support + `httpx2`      | FastAPI dependency wiring for plynth clients      |
| `salesforce` | Salesforce connector dependencies       | Typed Salesforce REST APIs, bulk, and AI services |

### Public API surface

Plynth treats package exports in `plynth.base` and `plynth.http` as the main
public contract boundaries for core usage.

- Prefer importing from these package roots instead of internal submodules.
- Internal module paths may evolve as long as public exports remain compatible.
- Compatibility and deprecation policy is defined in [ADR-0027](docs/architecture/adr/0027-public-api-compatibility-and-deprecation-policy.md).

## Salesforce connector

`plynth[salesforce]` ships a ready-to-use Salesforce REST API integration
with typed query services, Bulk API 2.0, AI APIs, and sync/async support:

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

## Generic LLM connector

`plynth.connectors.llm` provides a provider-agnostic contract for:

- neutral message and completion models,
- sync and async service parity,
- streaming chunk parsing helpers,
- optional tool-calling primitives.

Use it with any API that can map to the generic contract, while keeping
provider-specific fields in opaque `provider_extensions` payloads.

## Project Status

Current public release line:

- `0.1.0`: clean core foundation
- `0.2.0`: Salesforce connector baseline
- `0.2.1`: patch release
- `0.3.0`: streaming response support
- `0.4.0`: Salesforce Models and Agent APIs
- `0.5.0`: raw response access and throttle governance

## Documentation

- [README](https://github.com/eschaar/plynth/blob/main/README.md)
- [Changelog](https://github.com/eschaar/plynth/blob/main/CHANGELOG.md)
- [Architecture ADRs](https://github.com/eschaar/plynth/tree/main/docs/architecture/adr)
- [Salesforce connector docs](https://github.com/eschaar/plynth/tree/main/docs/connectors/salesforce)

## License

MIT
