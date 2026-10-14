# How to query Salesforce records

## Basic SOQL query

```python
result = sf.query().query("SELECT Id, Name FROM Account LIMIT 10")

for record in result.records:
    print(record["Id"], record["Name"])
```

`result` is a `SalesforceQueryResponse`. Key attributes:

| Attribute          | Type          | Description                                 |
| ------------------ | ------------- | ------------------------------------------- |
| `records`          | `list[dict]`  | The record data                             |
| `total_size`       | `int`         | Total matching records (not just this page) |
| `done`             | `bool`        | `True` when all pages have been fetched     |
| `next_records_url` | `str \| None` | Cursor URL for the next page                |

## Fetch all pages automatically

```python
result = sf.query().query_all("SELECT Id, Name FROM Contact")
print(f"Total: {result.total_size}")
for record in result.records:
    process(record)
```

`query_all` follows `nextRecordsUrl` until `done` is `True` and returns a
`SalesforceQueryResponse` with `done=True`, `next_records_url=None`, and
all records merged into `records`.

## Manual pagination

```python
page = sf.query().query("SELECT Id, Name FROM Account")
while not page.done:
    page = sf.query().query_more_from_id(page.next_records_url)
    for record in page.records:
        process(record)
```

## Include archived/deleted records

```python
result = sf.query().query(
    "SELECT Id, Name, IsDeleted FROM Account WHERE IsDeleted = true",
    include_deleted=True,
)
```

## Query records updated since a timestamp

```python
from datetime import datetime, timezone

svc = sf.object_query("Account")
result = svc.query_updated_since(
    since=datetime(2024, 1, 1, tzinfo=timezone.utc),
    fields=["Id", "Name", "LastModifiedDate"],
)
```

This uses the `LastModifiedDate` field by default. Pass `timestamp_field`
to override.

## SOQL helpers

Build safe queries without manual string formatting:

```python
from plynt.connectors.salesforce.helpers import (
    build_select_soql,
    escape_sosl,
    format_soql,
)

# Safe parameterised query
soql = format_soql("SELECT Id FROM Account WHERE Name = :name", name="Acme & Co")
# → SELECT Id FROM Account WHERE Name = 'Acme & Co'

# Build a SELECT from a field list
soql = build_select_soql("Account", ["Id", "Name", "Industry"])
# → SELECT Id, Name, Industry FROM Account
```

## Async

```python
result = await sf.query().query("SELECT Id FROM Account LIMIT 5")
```

All query methods have async parity on `AsyncSalesforceQueryService`.
