# How to handle Salesforce errors

## Exception hierarchy

```text
SalesforceAPIError                     # base for all API errors
├── SalesforceValidationError          # REQUIRED_FIELD_MISSING, FIELD_INTEGRITY_EXCEPTION
├── SalesforceDuplicateError           # DUPLICATES_DETECTED
├── SalesforceNotFoundError            # NOT_FOUND, ENTITY_IS_DELETED
├── SalesforceSessionExpiredError      # INVALID_SESSION_ID
├── SalesforcePermissionError          # INSUFFICIENT_ACCESS_*
├── SalesforceLockError                # UNABLE_TO_LOCK_ROW
├── SalesforceMalformedQueryError      # MALFORMED_QUERY
├── SalesforceInvalidFieldQueryError   # INVALID_FIELD
├── SalesforceInvalidTypeQueryError    # INVALID_TYPE
└── SalesforceQueryResponseError       # unexpected query response structure

BulkJobTimeoutError                    # bulk job did not complete in time
MetadataDeployTimeoutError             # metadata deploy timed out
SalesforceBulkJobError                 # bulk job completed with errors
SalesforceMetadataDeployError          # deploy completed with failures
```

## Catch a specific error

```python
from plynth.connectors.salesforce.errors import (
    SalesforceNotFoundError,
    SalesforceValidationError,
)

try:
    sf.sobject("Contact").get("0030000000INVALID")
except SalesforceNotFoundError:
    print("Record not found")
except SalesforceValidationError as e:
    for err in e.errors:
        print(f"  [{err.error_code}] {err.message} — fields: {err.fields}")
```

## Inspect error details

All `SalesforceAPIError` subclasses expose:

| Attribute     | Type                 | Description                                     |
| ------------- | -------------------- | ----------------------------------------------- |
| `errors`      | `list[SObjectError]` | All parsed error objects from the response body |
| `status_code` | `int`                | HTTP status code                                |

`SObjectError` has:

| Attribute    | Type        | Description                                           |
| ------------ | ----------- | ----------------------------------------------------- |
| `error_code` | `str`       | Salesforce error code (e.g. `REQUIRED_FIELD_MISSING`) |
| `message`    | `str`       | Human-readable message                                |
| `fields`     | `list[str]` | Fields involved (empty for non-field errors)          |

## Catch all Salesforce API errors

```python
from plynth.connectors.salesforce.errors import SalesforceAPIError

try:
    result = sf.query().query(soql)
except SalesforceAPIError as e:
    print(f"Salesforce error {e.status_code}: {e.errors[0].error_code}")
```

## Session expiry

`SalesforceSessionExpiredError` is raised when Salesforce returns
`INVALID_SESSION_ID`. This typically means the access token was revoked
externally. The auth middleware will refresh automatically on the next
attempt if the token is expired by TTL — but not if it was manually revoked.

```python
from plynth.connectors.salesforce.errors import SalesforceSessionExpiredError

try:
    sf.sobject("Account").get(record_id)
except SalesforceSessionExpiredError:
    # Re-initialise the client or alert operations
    raise
```

## Middleware errors

These are raised by middleware *before* a request reaches Salesforce:

```python
from plynth.middleware.circuit_breaker import CircuitBreakerOpenError

try:
    result = sf.query().query(soql)
except CircuitBreakerOpenError as e:
    print(f"Circuit open, retry after {e.retry_after_seconds:.0f}s")
```
