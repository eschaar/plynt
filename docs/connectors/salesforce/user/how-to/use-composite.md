# Use composite and batch requests

`SalesforceCompositeService` bundles multiple REST sub-requests into a
single HTTP round-trip. Use it to reduce latency and API call consumption
when you need to create or query several records together.

## Prerequisites

A configured `SalesforceAPIFacade`:

```python
from plynth.connectors.salesforce.facade import SalesforceAPIFacade

sf = SalesforceAPIFacade(client)
comp = sf.composite()
```

______________________________________________________________________

## Composite requests

`composite()` sends up to 25 sub-requests and allows later requests to
reference the response of earlier ones via `reference_id`:

```python
from plynth.connectors.salesforce.composite import CompositeSubrequest

response = comp.composite(
    requests=[
        CompositeSubrequest(
            method="POST",
            url="/services/data/v60.0/sobjects/Account",
            reference_id="newAccount",
            body={"Name": "Composite Corp"},
        ),
        CompositeSubrequest(
            method="POST",
            url="/services/data/v60.0/sobjects/Contact",
            reference_id="newContact",
            body={
                "LastName": "Example",
                "AccountId": "@{newAccount.id}",
            },
        ),
    ],
)

for sub in response.composite_response:
    print(sub.reference_id, sub.http_status_code)
```

The `@{newAccount.id}` syntax tells Salesforce to substitute the `id`
from the first sub-request's response into the second one.

### Roll back on any failure

Set `all_or_none=True` to roll back the entire composite request if any
sub-request fails:

```python
response = comp.composite(requests=subrequests, all_or_none=True)
if response.has_errors:
    print("Rolled back")
```

______________________________________________________________________

## Batch requests

`batch()` sends up to 25 independent sub-requests. Unlike `composite()`,
batch requests cannot reference each other's results:

```python
from plynth.connectors.salesforce.composite import CompositeBatchSubrequest

response = comp.batch(
    requests=[
        CompositeBatchSubrequest(
            method="GET",
            url="/services/data/v60.0/sobjects/Account/001Dn000001aaa",
        ),
        CompositeBatchSubrequest(
            method="GET",
            url="/services/data/v60.0/sobjects/Contact/003Dn000001bbb",
        ),
    ],
)

for result in response.results:
    print(result.status_code, result.result)
```

Stop processing remaining sub-requests as soon as one fails:

```python
response = comp.batch(requests=subrequests, halt_on_error=True)
```

______________________________________________________________________

## Tree requests (bulk parent-child insert)

`tree()` creates up to 200 records of one SObject type in a single call.
Use it to insert parent records together with their children:

```python
response = comp.tree(
    object_name="Account",
    records=[
        {
            "attributes": {"type": "Account", "referenceId": "ref1"},
            "Name": "Tree Corp",
            "Contacts": {
                "records": [
                    {
                        "attributes": {"type": "Contact", "referenceId": "ref1c1"},
                        "LastName": "Child",
                        "Email": "child@tree.com",
                    }
                ]
            },
        }
    ],
)

if not response.has_errors:
    for result in response.results:
        print(result.reference_id, result.id)
```

______________________________________________________________________

## Error handling

All three methods set `has_errors` on the response object. Individual
sub-request errors appear in the respective `http_status_code` or
`errors` field:

```python
if response.has_errors:
    for sub in response.composite_response:
        if sub.http_status_code >= 400:
            print(f"{sub.reference_id}: HTTP {sub.http_status_code} — {sub.body}")
```

______________________________________________________________________

## Async

```python
from plynth.connectors.salesforce.facade import AsyncSalesforceAPIFacade

sf = AsyncSalesforceAPIFacade(async_client)
comp = sf.composite()

response = await comp.composite(requests=subrequests, all_or_none=True)
```

______________________________________________________________________

## When to use each method

| Method        | Max sub-requests | Cross-reference | Use case                                  |
| ------------- | ---------------- | --------------- | ----------------------------------------- |
| `composite()` | 25               | Yes             | Dependent creates/reads in one round-trip |
| `batch()`     | 25               | No              | Independent reads or writes in parallel   |
| `tree()`      | 200 records      | N/A             | Parent-child bulk insert                  |

______________________________________________________________________

## See also

- [Create, update, and delete SObject records](sobject-crud.md)
- [Run Bulk API operations](bulk.md) — for volumes above 200 records
- [Services reference](../reference/services.md)
