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
from plynt.connectors.salesforce.errors import (
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
from plynt.connectors.salesforce.errors import SalesforceAPIError

try:
    result = sf.query().query(soql)
except SalesforceAPIError as e:
    print(f"Salesforce error {e.status_code}: {e.errors[0].error_code}")
```

## Authentication endpoint failures

Salesforce client credentials, password, and JWT bearer middleware raise
`AuthenticationError` when the token endpoint returns a status other than 200.
This applies to both sync and async clients. These failures occur before a
Salesforce API call and are not `SalesforceAPIError` instances.

```python
from plynt.base import AuthenticationError

try:
    instance_url = auth.instance_url
except AuthenticationError as error:
    print(f"Authentication endpoint returned {error.status_code}")
```

For async middleware, use `await auth.get_instance_url()` instead.

The error retains the status code and an optional `response_body` attribute.
The body is excluded from messages and structured output; do not log it,
because authentication responses may contain sensitive data.

Existing `except RuntimeError` handlers still match. Code parsing the old
message must inspect `status_code` instead. Missing or empty `instance_url`
in a successful token response still raises `RuntimeError`.

See the [generic error contract](../../../../user/how-to/handle-errors.md)
for the shared transport and authentication error types.

## Session expiry

`SalesforceSessionExpiredError` is raised when Salesforce returns
`INVALID_SESSION_ID`. This typically means the access token was revoked
externally. The auth middleware will refresh automatically on the next
attempt if the token is expired by TTL — but not if it was manually revoked.

```python
from plynt.connectors.salesforce.errors import SalesforceSessionExpiredError

try:
    sf.sobject("Account").get(record_id)
except SalesforceSessionExpiredError:
    # Re-initialise the client or alert operations
    raise
```

## Middleware errors

These are raised by middleware *before* a request reaches Salesforce:

```python
from plynt.middleware.circuit_breaker import CircuitBreakerOpenError

try:
    result = sf.query().query(soql)
except CircuitBreakerOpenError as e:
    print(f"Circuit open, retry after {e.retry_after_seconds:.0f}s")
```
