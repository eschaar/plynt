# Error reference

## Exception hierarchy

```text
SalesforceAPIError                     # base for all Salesforce API errors
├── SalesforceValidationError          # validation failures
├── SalesforceDuplicateError           # duplicate-detection rule triggered
├── SalesforceNotFoundError            # record does not exist or was deleted
├── SalesforceSessionExpiredError      # access token has been revoked
├── SalesforcePermissionError          # caller lacks the required permission
├── SalesforceLockError                # row lock conflict
├── SalesforceMalformedQueryError      # SOQL/SOSL syntax error
├── SalesforceInvalidFieldQueryError   # unknown or inaccessible field in query
├── SalesforceInvalidTypeQueryError    # unknown or inaccessible object in query
└── SalesforceQueryResponseError       # query response had an unexpected structure

BulkJobTimeoutError                    # raised when bulk job polls exceed timeout
MetadataDeployTimeoutError             # raised when metadata deploy polls exceed timeout
SalesforceBulkJobError                 # bulk job completed with errors
SalesforceMetadataDeployError          # metadata deploy completed with failures
```

## Exception details

### `SalesforceAPIError`

Base class. All subclasses expose:

| Attribute     | Type                 | Description                                       |
| ------------- | -------------------- | ------------------------------------------------- |
| `errors`      | `list[SObjectError]` | Parsed error objects from the Salesforce response |
| `status_code` | `int`                | HTTP status code                                  |

### `SObjectError`

| Attribute    | Type        | Description                                                  |
| ------------ | ----------- | ------------------------------------------------------------ |
| `error_code` | `str`       | Salesforce error code string (e.g. `REQUIRED_FIELD_MISSING`) |
| `message`    | `str`       | Human-readable error message                                 |
| `fields`     | `list[str]` | Fields involved in the error (empty for non-field errors)    |

### `SalesforceValidationError`

HTTP 400. Raised when a DML operation violates a required field, field
integrity constraint, or custom validation rule. Check `errors[0].fields`
to identify the offending fields.

**Common `error_code` values:** `REQUIRED_FIELD_MISSING`,
`FIELD_INTEGRITY_EXCEPTION`, `FIELD_CUSTOM_VALIDATION_EXCEPTION`,
`STRING_TOO_LONG`.

### `SalesforceDuplicateError`

HTTP 400. Raised when Salesforce's duplicate management rules detect a
potential duplicate. The `errors` list may include match result details.

**Common `error_code` values:** `DUPLICATES_DETECTED`.

### `SalesforceNotFoundError`

HTTP 404. Raised when the requested record does not exist, has been
deleted, or the caller cannot see it.

**Common `error_code` values:** `NOT_FOUND`, `ENTITY_IS_DELETED`,
`INVALID_CROSS_REFERENCE_KEY`.

### `SalesforceSessionExpiredError`

HTTP 401. Raised when the access token has been manually revoked or has
expired outside the normal TTL window. The auth middleware refreshes
tokens on normal expiry, but cannot recover from manual revocation.

**Common `error_code` values:** `INVALID_SESSION_ID`.

### `SalesforcePermissionError`

HTTP 403. Raised when the connected user lacks the profile permission or
sharing access to complete the operation.

**Note:** HTTP 403 with `REQUEST_LIMIT_EXCEEDED` is *also* raised as
`SalesforcePermissionError` (or a dedicated subclass in future versions).
Check `error_code` to distinguish quota exhaustion from a permission error.

**Common `error_code` values:** `INSUFFICIENT_ACCESS_ON_CROSS_REFERENCE_ENTITY`,
`INSUFFICIENT_ACCESS_OR_READONLY`, `REQUEST_LIMIT_EXCEEDED`.

### `SalesforceLockError`

HTTP 400 or 503. Raised when Salesforce cannot acquire a row lock due to
concurrent modifications.

**Common `error_code` values:** `UNABLE_TO_LOCK_ROW`.

### Query errors

| Class                              | When raised                                                 |
| ---------------------------------- | ----------------------------------------------------------- |
| `SalesforceMalformedQueryError`    | SOQL or SOSL syntax error                                   |
| `SalesforceInvalidFieldQueryError` | Query references an unknown or inaccessible field           |
| `SalesforceInvalidTypeQueryError`  | Query references an unknown or inaccessible object type     |
| `SalesforceQueryResponseError`     | Salesforce returned a query response in an unexpected shape |

### Bulk errors

| Class                    | When raised                                                   |
| ------------------------ | ------------------------------------------------------------- |
| `BulkJobTimeoutError`    | Polling for a bulk job result exceeded the configured timeout |
| `SalesforceBulkJobError` | Bulk job completed but contained row-level errors             |

### Metadata errors

| Class                           | When raised                                             |
| ------------------------------- | ------------------------------------------------------- |
| `MetadataDeployTimeoutError`    | Metadata deploy polling exceeded the configured timeout |
| `SalesforceMetadataDeployError` | Deploy completed but contained component failures       |
