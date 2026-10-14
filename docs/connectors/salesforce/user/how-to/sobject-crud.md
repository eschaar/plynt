# Create, update, and delete SObject records

This guide covers all CRUD operations on Salesforce standard and custom
objects via `SalesforceObjectService`.

## Prerequisites

A configured `SalesforceAPIFacade`. See
[Tutorial 1](../tutorials/01-connect-and-query.md) for setup.

```python
from plynt.connectors.salesforce.facade import SalesforceAPIFacade

sf = SalesforceAPIFacade(client)
svc = sf.sobject("Contact")
```

______________________________________________________________________

## Get a record by ID

```python
contact = svc.get("003Dn000001abcDIAQ")
print(contact["LastName"])
```

Request only specific fields to reduce payload size:

```python
contact = svc.get("003Dn000001abcDIAQ", fields=["Id", "FirstName", "LastName", "Email"])
```

Raises `NotFoundError` (404) when the ID does not exist, and
`ForbiddenError` (403) when the running user lacks read access.

______________________________________________________________________

## Get a record by external ID

Retrieve a record using a custom external ID field instead of the
Salesforce record ID:

```python
contact = svc.get_by_external_id("Employee_Number__c", "EMP-4271")
```

Raises `NotFoundError` when no matching record exists.

______________________________________________________________________

## Create a record

```python
result = svc.create(
    {
        "FirstName": "Jane",
        "LastName": "Doe",
        "Email": "jane.doe@example.com",
    }
)
print(result.id)  # "003Dn000001xyzABC"
print(result.success)  # True
```

`create()` returns a `SObjectCreateResult` with `id` and `success` fields.
Raises `BadRequestError` (400) for missing required fields and
`UnprocessableEntityError` (422) for validation rule failures.

______________________________________________________________________

## Update a record

`update()` sends a PATCH request. Pass only the fields you want to change:

```python
svc.update("003Dn000001abcDIAQ", {"Phone": "+31 20 000 0000"})
```

Returns `None` on success. Raises `NotFoundError` or `ForbiddenError` on
failure.

______________________________________________________________________

## Upsert by external ID

Create or update a record based on an external ID field. Salesforce decides
whether to insert or update:

```python
result = svc.upsert(
    "Employee_Number__c",
    "EMP-4271",
    {"FirstName": "Jane", "LastName": "Doe", "Email": "jane@example.com"},
)
if result is not None:
    print(f"Created: {result.id}")
else:
    print("Updated existing record")
```

Returns `SObjectCreateResult` when the record was created, `None` when an
existing record was updated.

______________________________________________________________________

## Delete a record

```python
svc.delete("003Dn000001abcDIAQ")
```

Returns `None` on success. Raises `NotFoundError` when the ID does not
exist.

______________________________________________________________________

## Describe an SObject

Retrieve full metadata for an SObject type — fields, picklist values,
relationships, and more:

```python
description = svc.describe()
field_names = [f["name"] for f in description["fields"]]
```

______________________________________________________________________

## Get basic SObject metadata

Lighter than `describe()` — returns URLs and basic metadata without the
full field list:

```python
meta = svc.metadata()
print(meta["label"])
```

______________________________________________________________________

## Describe a record layout

```python
layout = svc.describe_layout("01IXX0000004CXX")
```

______________________________________________________________________

## Track deleted records

Retrieve records soft-deleted within a time window. Useful for incremental
sync:

```python
from datetime import datetime, timedelta, timezone

now = datetime.now(timezone.utc)
result = svc.deleted(now - timedelta(hours=1), now)
for record in result["deletedRecords"]:
    print(record["id"])
```

______________________________________________________________________

## Track updated records

Retrieve IDs of records updated within a time window:

```python
result = svc.updated(now - timedelta(hours=1), now)
for record_id in result["ids"]:
    print(record_id)
```

______________________________________________________________________

## Async

All methods have async equivalents. Use `AsyncSalesforceAPIFacade` and
`await` each call:

```python
from plynt.connectors.salesforce.facade import AsyncSalesforceAPIFacade

sf = AsyncSalesforceAPIFacade(async_client)
svc = sf.sobject("Contact")

result = await svc.create({"LastName": "Async", "Email": "a@example.com"})
contact = await svc.get(result.id)
await svc.delete(result.id)
```

______________________________________________________________________

## See also

- [Query records with SOQL](query-records.md)
- [Run Bulk API operations](bulk.md) — for large-volume inserts and updates
- [Handle Salesforce errors](handle-errors.md)
- [Services reference](../reference/services.md)
