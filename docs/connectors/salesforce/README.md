# Salesforce Integration Guide

This guide describes how to use the Salesforce integration in Plynth.
It is intentionally self-contained to simplify a future extraction into a
standalone package.

## Scope

The current Salesforce integration focuses on the standard SObject REST API,
with sync and async support.

Implemented capabilities include:

- SObject CRUD operations
- External ID lookup and upsert
- SObject metadata and describe endpoints
- Layout, deleted-window, and updated-window endpoints
- Utility REST endpoints: limits, tooling_execute, objects
- Identity access primitives: generic user retrieval/listing and permission
  set assignment operations
- Search capability: SOSL search and quick_search
- Typed Salesforce error mapping
- OAuth2 client credentials flow; OAuth2 password flow (implemented but
  deprecated by Salesforce — blocked by default in orgs created Summer '23
  or later; migrate to client credentials or JWT Bearer)
- Ergonomic facade for object-bound services

## Main Components

- Client layer:
  - SalesforceAPIClient
  - AsyncSalesforceAPIClient
- Service layer:
  - SalesforceObjectService
  - AsyncSalesforceObjectService
  - SalesforceQueryService
  - AsyncSalesforceQueryService
  - SalesforceSearchService
  - AsyncSalesforceSearchService
  - SalesforceUtilityService
  - AsyncSalesforceUtilityService
- Facade layer:
  - SalesforceAPIFacade
  - AsyncSalesforceAPIFacade

## Package Layout

The Salesforce connector is organized as focused subpackages for long-term
maintainability:

- `plynth.connectors.salesforce.auth`
- `plynth.connectors.salesforce.bulk`
- `plynth.connectors.salesforce.identity`
- `plynth.connectors.salesforce.lookup`
- `plynth.connectors.salesforce.models`
- `plynth.connectors.salesforce.query`
- `plynth.connectors.salesforce.sobject`

Test structure mirrors this package layout under
`tests/connectors/salesforce/` (for example `lookup/`, `bulk/`, `query/`,
`auth/`, `identity/`, `models/`, and `sobject/`).

## Sync Quickstart (Facade)

```python
from plynth.http.transport import HttpxSyncTransport
from plynth.connectors.salesforce.auth import (
    SalesforceClientCredentialsAuthMiddleware,
)
from plynth.connectors.salesforce.client import SalesforceAPIClient
from plynth.connectors.salesforce.facade import SalesforceAPIFacade

auth = SalesforceClientCredentialsAuthMiddleware(
    client_id="...",
    client_secret="...",
    token_url="https://login.salesforce.com/services/oauth2/token",
)
transport = HttpxSyncTransport(middlewares=[auth])
client = SalesforceAPIClient(auth=auth, transport=transport)

facade = SalesforceAPIFacade(client)
account = facade.sobject("Account")

record = account.get("001xx000003GYWJAA4")
created = account.create({"Name": "ACME Corp"})
account.update(created.id, {"Phone": "+31201234567"})
```

## Async Quickstart (Facade)

```python
from plynth.http.transport import HttpxAsyncTransport
from plynth.connectors.salesforce.auth import (
    AsyncSalesforceClientCredentialsAuthMiddleware,
)
from plynth.connectors.salesforce.client import AsyncSalesforceAPIClient
from plynth.connectors.salesforce.facade import AsyncSalesforceAPIFacade

auth = AsyncSalesforceClientCredentialsAuthMiddleware(
    client_id="...",
    client_secret="...",
    token_url="https://login.salesforce.com/services/oauth2/token",
)
transport = HttpxAsyncTransport(middlewares=[auth])
client = AsyncSalesforceAPIClient(auth=auth, transport=transport)

facade = AsyncSalesforceAPIFacade(client)
account = facade.sobject("Account")

record = await account.get("001xx000003GYWJAA4")
created = await account.create({"Name": "ACME Corp"})
await account.update(created.id, {"Phone": "+31201234567"})
```

## JWT Bearer Example (Recommended for Server-to-Server)

JWT Bearer uses an RSA key pair:

- Upload the public certificate to the Salesforce Connected App.
- Keep the private key in your runtime secret store or environment variable.
- Sign JWT assertions in the application; never expose or commit the private
  key.

For Salesforce JWT Bearer, a self-signed certificate is commonly used.
Compliance policy in your organization can still require CA-signed material.

```python
import os

from plynth.http.transport import HttpxSyncTransport
from plynth.connectors.salesforce.auth import SalesforceJWTBearerAuthMiddleware
from plynth.connectors.salesforce.client import SalesforceAPIClient

auth = SalesforceJWTBearerAuthMiddleware(
    client_id=os.environ["SF_CLIENT_ID"],
    username=os.environ["SF_USERNAME"],
    private_key=os.environ["SF_JWT_PRIVATE_KEY_PEM"],
    token_url="https://login.salesforce.com/services/oauth2/token",
)
transport = HttpxSyncTransport(middlewares=[auth])
client = SalesforceAPIClient(auth=auth, transport=transport)
```

Sandbox orgs should use:

```python
token_url = "https://test.salesforce.com/services/oauth2/token"
```

## Direct Session Token Injection (Edge Case)

Plynth supports a direct session token mode via:

- SalesforceSessionAuthMiddleware (sync)
- AsyncSalesforceSessionAuthMiddleware (async)

This mode is intentionally narrow and should only be used when token
management is already handled outside Plynth.

### What this mode does

In direct session mode, Plynth does only two things:

- injects Authorization: Bearer token-value on outgoing requests
- uses the provided Salesforce instance_url for request routing

Plynth does not do token endpoint calls, token refresh, token expiry handling,
or token cache lifecycle in this mode.

### Why this exists

This is useful for integration architectures where another component already
owns Salesforce token lifecycle, for example:

- API gateway or integration layer that injects a valid Salesforce token
- internal token broker service that fetches and refreshes Salesforce tokens
- short-lived jobs (batch/serverless) that receive a pre-fetched token

In these cases, duplicating OAuth lifecycle logic inside Plynth can create
conflicting responsibilities and stale-token race behavior.

### Important clarification

Even in this mode, the access token is typically still Salesforce-issued.
"Extern managed" means lifecycle ownership is external, not token issuer.

### When to use which auth mode

Use OAuth/JWT auth middleware when:

- Plynth must fetch tokens itself
- Plynth must refresh tokens itself
- Plynth should own token caching and retry behavior

Use direct session middleware when:

- your application already has a valid Salesforce access token
- token refresh is handled by another trusted component
- you want Plynth to remain stateless with respect to token lifecycle

### Risks and guardrails

Direct session mode is an advanced path. Make sure:

- token TTL and refresh strategy are guaranteed upstream
- token rotation is synchronized with request execution paths
- instance_url belongs to the same org/context as the provided token

If these conditions are not guaranteed, prefer OAuth/JWT middleware in Plynth.

### Minimal direct-session example

```python
from plynth.http.transport import HttpxSyncTransport
from plynth.connectors.salesforce.auth import SalesforceSessionAuthMiddleware
from plynth.connectors.salesforce.client import SalesforceAPIClient

auth = SalesforceSessionAuthMiddleware(
  access_token="<salesforce_access_token>",
  instance_url="https://myorg.my.salesforce.com",
)
transport = HttpxSyncTransport(middlewares=[auth])
client = SalesforceAPIClient(auth=auth, transport=transport)
```

## Direct Service Usage

If you prefer explicit wiring without facade:

- Instantiate SalesforceObjectService or AsyncSalesforceObjectService directly.
- Use the same client/auth setup as above.

## Utility Endpoints

Use the utility service for object-independent Salesforce REST endpoints.

```python
util = facade.utility()

limits = util.limits()
tooling = util.tooling_execute("query", params={"q": "SELECT Id FROM ApexClass"})
catalog = util.objects()  # returns SalesforceGlobalDescribeResponse
```

`objects()` calls `GET /sobjects/` and returns all SObject types available on
the org, together with their capabilities (queryable, createable, etc.).

## Composite Primitives

Use the composite service when you want to bundle generic Salesforce REST
requests without building business workflows into the connector itself.

Supported building blocks:

- `composite(...)` for chained subrequests with `referenceId` linking
- `batch(...)` for grouped REST requests
- `tree(...)` for hierarchical parent/child creates

Example:

```python
from plynth.connectors.salesforce.composite import CompositeSubrequest

composite = facade.composite()

result = composite.composite(
  [
    CompositeSubrequest.model_validate(
      {
        "method": "POST",
        "url": "/services/data/v59.0/sobjects/Account",
        "referenceId": "NewAccount",
        "body": {"Name": "Acme"},
      }
    ),
    CompositeSubrequest.model_validate(
      {
        "method": "POST",
        "url": "/services/data/v59.0/sobjects/Contact",
        "referenceId": "NewContact",
        "body": {
          "LastName": "Doe",
          "AccountId": "@{NewAccount.id}",
        },
      }
    ),
  ],
  all_or_none=True,
)
```

Keep the actual orchestration logic in the consuming application layer. The
connector only provides the generic primitives.

See [SF-0007](architecture/adr/sf-0007-composite-rest-primitives.md) for the decision and
scope.

## Lookup Convenience Services

The Salesforce connector includes lookup-oriented DX conveniences for
high-frequency, repeatable, non-business-specific identifier resolution.

Rule for adding new lookup conveniences:

- only add a lookup convenience for high-frequency, repeatable,
  non-business-specific patterns
- keep lookup services thin wrappers over generic query/client layers
- do not add business logic or domain policies to lookup services

Current lookup conveniences live in `plynth.connectors.salesforce.lookup`:

- `SalesforceRecordTypeLookupService` / `AsyncSalesforceRecordTypeLookupService`
- `SalesforceUserLookupService` / `AsyncSalesforceUserLookupService`
- `SalesforcePricebookLookupService` /
  `AsyncSalesforcePricebookLookupService`
- `SalesforceQueueLookupService` / `AsyncSalesforceQueueLookupService`
- `SalesforceProfileLookupService` / `AsyncSalesforceProfileLookupService`

Facade entry points:

- `facade.lookup(LookupType.RECORD_TYPE)`
- `facade.lookup(LookupType.USER)`
- `facade.lookup(LookupType.PRICEBOOK)`
- `facade.lookup(LookupType.QUEUE)`
- `facade.lookup(LookupType.PROFILE)`

Example:

```python
from plynth.connectors.salesforce.facade import LookupType

lookup = facade.lookup(LookupType.RECORD_TYPE)
record_type = lookup.get_by_developer_name("Account", "Business")

user_lookup = facade.lookup(LookupType.USER)
integration_user = user_lookup.get_by_username("integration@example.com")

pricebook_lookup = facade.lookup(LookupType.PRICEBOOK)
standard_pricebook = pricebook_lookup.get_standard(is_active=True)

queue_lookup = facade.lookup(LookupType.QUEUE)
support_queue = queue_lookup.get_by_developer_name("Support_Queue")

profile_lookup = facade.lookup(LookupType.PROFILE)
profile = profile_lookup.get_by_name("System Administrator")
```

## Search Endpoints

Use the dedicated search service for SOSL queries.

```python
from plynth.connectors.salesforce.helpers import escape_sosl

search = facade.search()

# Full SOSL expression
result = search.search(
    "FIND {Acme Inc} IN NAME FIELDS RETURNING Account(Id, Name)"
)

# Convenience wrapper that wraps the term in FIND {…} automatically
result = search.quick_search("Acme")

for record in result.search_records:
    print(record.sobject_type, record.id)
```

## Query and Search Helpers

The `plynth.connectors.salesforce.helpers` module provides safe formatting
utilities for SOQL and SOSL expressions.

```python
from plynth.connectors.salesforce.helpers import (
    escape_sosl,
    format_soql,
    is_salesforce_id,
    validate_salesforce_id,
)

# Escape user input for safe embedding in SOSL FIND clauses
term = escape_sosl("O'Brien & Co (Ltd.)")  # → "O\'Brien \& Co \(Ltd\.\)"

# Format a SOQL query with safely-escaped named parameters
soql = format_soql(
    "SELECT Id FROM Account WHERE Name = :name AND Active__c = :active",
    name="O'Brien",
    active=True,
)

# Validate Salesforce record IDs (15 or 18 characters)
is_salesforce_id("001xx000003GYWJAA4")  # True
validate_salesforce_id("not-an-id")    # raises ValueError
```

## Query Service Usage

Use the query service for shipped SOQL execution and pagination helpers.

### Global SOQL query service

```python
query_svc = facade.query()

page = query_svc.query(
    "SELECT Id, Name FROM Account WHERE CreatedDate = LAST_N_DAYS:30"
)

deleted_page = query_svc.query(
    "SELECT Id, IsDeleted FROM Account WHERE IsDeleted = true",
    include_deleted=True,
)

result = query_svc.query_all(
    "SELECT Id, Name FROM Account ORDER BY CreatedDate DESC"
)

result_with_deleted = query_svc.query_all(
    "SELECT Id, IsDeleted FROM Account ORDER BY LastModifiedDate DESC",
    include_deleted=True,
)
```

### Pagination helpers

```python
next_page = query_svc.query_more(page.next_records_url)
next_page_by_id = query_svc.query_more_from_id(
    page.next_records_url.rsplit("/", 1)[-1]
)

for page in query_svc.query_all_iter("SELECT Id, Name FROM Lead"):
    for record in page.records:
        process(record)
```

### Object-scoped query service

```python
lead_query = facade.object_query("Lead")

page = lead_query.query(fields=["Id", "Email"], where="Email = 'john@example.com'")
result = lead_query.query_all(
    fields=["Id", "Email", "FirstName", "LastName"],
    where="Email = 'john@example.com'",
)
```

The query service is shipped and documented in [SF-0003](architecture/adr/sf-0003-query-service-design.md).

### Incremental object query

Use `query_updated_since()` on the object-scoped query service to fetch
records modified after a given timestamp. The `since` datetime must be
timezone-aware; passing a naive datetime raises `ValueError`.

```python
from datetime import datetime, timezone

lead_query = facade.object_query("Lead")

updated = lead_query.query_updated_since(
    since=datetime(2026, 1, 1, tzinfo=timezone.utc),
    fields=["Id", "Email", "SystemModstamp"],
)
for record in updated.records:
    process(record)
```

The default timestamp field is `SystemModstamp`. Override with
`timestamp_field=` when the SObject uses a custom tracking field.

The query API is intentionally narrow: raw SOQL, pagination helpers, and
object-scoped convenience accessors. Business-specific query builders remain
out of scope for the generic connector.

If you need a higher-level query abstraction, build it in the consuming
application on top of [SF-0003](architecture/adr/sf-0003-query-service-design.md).

## API Scope Note

The utility service in this module targets Salesforce Platform REST API
endpoints only. It does not cover SOAP, Bulk, or Pub/Sub APIs.

## Authentication Modes

Supported auth middlewares:

- SalesforceClientCredentialsAuthMiddleware
- SalesforcePasswordAuthMiddleware
- AsyncSalesforceClientCredentialsAuthMiddleware
- AsyncSalesforcePasswordAuthMiddleware

Use one flow per client instance.

## Error Handling

Salesforce error payloads are mapped to typed exceptions rooted at
SalesforceAPIError.

See ADR:

- [SF-0001 Error Mapping](architecture/adr/sf-0001-error-mapping.md)

## Facade Decision

Facade naming and architecture decision:

- [SF-0002 Salesforce facade ergonomics](architecture/adr/sf-0002-sobject-api-facade.md)

## Roadmap

For feature planning, ideas, and extraction sequencing, see:

- [Salesforce Roadmap](product/roadmap.md)
- [Salesforce Extraction Plan](product/extraction-plan.md)
- [Project Roadmap](../../product/roadmap.md)
- [VCR Testsupport Guide](../../../src/plynth/testsupport/vcr/README.md)
