# Search with SOSL

This guide covers full-text search across multiple Salesforce SObject types
using `SalesforceSearchService` and the SOSL query language.

## Prerequisites

A configured `SalesforceAPIFacade`:

```python
from plynth.connectors.salesforce.facade import SalesforceAPIFacade

sf = SalesforceAPIFacade(client)
svc = sf.search()
```

______________________________________________________________________

## Run a SOSL search

Pass a full SOSL string to `search()`:

```python
response = svc.search("FIND {Acme} IN ALL FIELDS RETURNING Account(Id, Name), Contact(Id, Name)")
for record in response.search_records:
    print(record["Id"], record["Name"])
```

`search()` returns a `SalesforceSearchResponse` with a `search_records`
list. Each entry is a `dict` containing the fields you requested.

Salesforce returns `[]` (empty list) when no records match — not an error.

______________________________________________________________________

## Quick search

`quick_search()` wraps your term inside `FIND {term} IN ALL FIELDS RETURNING` without specifying SObject types.
Salesforce returns results across all searchable objects:

```python
response = svc.quick_search("Doe")
for record in response.search_records:
    print(record)
```

Use `search()` with an explicit `RETURNING` clause when you need to control
which objects and fields are returned.

______________________________________________________________________

## Limit results to specific objects and fields

```python
sosl = (
    "FIND {jane@example.com} "
    "IN EMAIL FIELDS "
    "RETURNING Contact(Id, FirstName, LastName, Email), Lead(Id, Name, Email)"
)
response = svc.search(sosl)
```

SOSL `IN` clauses: `ALL FIELDS`, `NAME FIELDS`, `EMAIL FIELDS`,
`PHONE FIELDS`.

______________________________________________________________________

## Handle empty results

`search_records` is always a list — check its length rather than testing
for `None`:

```python
response = svc.search("FIND {NoResultsExpected12345} IN ALL FIELDS RETURNING Contact")
if not response.search_records:
    print("No matches")
```

______________________________________________________________________

## Async

```python
from plynth.connectors.salesforce.facade import AsyncSalesforceAPIFacade

sf = AsyncSalesforceAPIFacade(async_client)
svc = sf.search()

response = await svc.search("FIND {Acme} IN NAME FIELDS RETURNING Account(Id, Name)")
```

______________________________________________________________________

## See also

- [Query records with SOQL](query-records.md) — structured queries on a
  single object
- [Services reference](../reference/services.md)
