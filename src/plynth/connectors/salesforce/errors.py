"""Typed exceptions for the Salesforce Platform REST API.

Salesforce returns error details in the response body as a JSON list::

    [{"message": "Required fields are missing: [Name]",
      "errorCode": "REQUIRED_FIELD_MISSING",
      "fields": ["Name"]}]

This module maps Salesforce ``errorCode`` values to typed Python exceptions,
making it straightforward to handle specific failure modes without parsing raw
strings.  All exceptions carry the full ``errors`` list and the HTTP
``status_code`` from the response, so callers have complete context.

Exception hierarchy::

    SalesforceAPIError
    ├── SalesforceValidationError
    ├── SalesforceDuplicateError
    ├── SalesforceNotFoundError
    ├── SalesforceSessionExpiredError
    ├── SalesforcePermissionError
    └── SalesforceLockError

"""

from __future__ import annotations

import json

from pydantic import ValidationError

from plynth.base.response import Response
from plynth.connectors.salesforce.models import SObjectError

__all__ = [
    "BulkJobTimeoutError",
    "MetadataDeployTimeoutError",
    "SalesforceAPIError",
    "SalesforceBulkJobError",
    "SalesforceDuplicateError",
    "SalesforceLockError",
    "SalesforceMetadataDeployError",
    "SalesforceNotFoundError",
    "SalesforcePermissionError",
    "SalesforceSessionExpiredError",
    "SalesforceValidationError",
    "raise_for_salesforce_errors",
]


# ---------------------------------------------------------------------------
# Exception classes
# ---------------------------------------------------------------------------


class SalesforceAPIError(Exception):
    """Base exception for Salesforce REST API business-logic errors.

    Raised when the Salesforce API returns a response body containing a list
    of structured error objects (``errorCode`` + ``message`` + optional
    ``fields``).  The full parsed error list and the HTTP status code are
    always available on the exception instance.

    Attributes:
        errors: All parsed ``SObjectError`` entries from the response body.
        status_code: HTTP status code of the response.

    """

    def __init__(self, errors: list[SObjectError], status_code: int) -> None:
        """Initialize SalesforceAPIError."""
        self.errors = errors
        self.status_code = status_code
        first = errors[0] if errors else None
        code = first.error_code if first else "UNKNOWN"
        msg = first.message if first else "Salesforce API error"
        super().__init__(f"[{code}] {msg}")


class SalesforceValidationError(SalesforceAPIError):
    """Raised for Salesforce data-validation failures.

    Covers ``REQUIRED_FIELD_MISSING``, ``FIELD_CUSTOM_VALIDATION_EXCEPTION``,
    ``FIELD_INTEGRITY_EXCEPTION``, ``STRING_TOO_LONG``, and related codes.

    """


class SalesforceDuplicateError(SalesforceAPIError):
    """Raised when Salesforce detects a duplicate record.

    Covers ``DUPLICATE_VALUE``, ``DUPLICATES_DETECTED``,
    ``DUPLICATE_EXTERNAL_ID``.

    """


class SalesforceNotFoundError(SalesforceAPIError):
    """Raised when a referenced Salesforce record or object does not exist.

    Covers ``NOT_FOUND``, ``RECORD_NOT_FOUND``, ``ENTITY_IS_DELETED``,
    ``ENTITY_IS_ARCHIVED``, ``SCHEMA_OBJECT_NOT_FOUND``.

    """


class SalesforceSessionExpiredError(SalesforceAPIError):
    """Raised when the Salesforce session or access token is no longer valid.

    Covers ``INVALID_SESSION_ID``, ``SESSION_EXPIRED``,
    ``SESSION_INVALIDATED``, ``INVALID_ACCESS_TOKEN``, ``NO_ACCESS_TOKEN``,
    ``REFRESH_FAILED``.

    """


class SalesforcePermissionError(SalesforceAPIError):
    """Raised when the caller lacks the required Salesforce access rights.

    Covers ``INSUFFICIENT_ACCESS``,
    ``INSUFFICIENT_ACCESS_ON_CROSS_REFERENCE_ENTITY``,
    ``FORBIDDEN_EXCEPTION``, ``UNAUTHORIZED_EXCEPTION``, and related codes.

    """


class SalesforceLockError(SalesforceAPIError):
    """Raised when a Salesforce record is locked by another concurrent process.

    Covers ``UNABLE_TO_LOCK_RECORD``, ``UNABLE_TO_LOCK_ROW``,
    ``RECORD_LOCKED``.

    """


class SalesforceBulkJobError(SalesforceAPIError):
    """Raised when a Bulk API 2.0 job ends in ``Failed`` or ``Aborted`` state.

    Attributes:
        job_id: The Salesforce bulk job ID.
        errors: Always an empty list (bulk job errors are not SObject errors).
        status_code: Always ``0`` (not an HTTP-level error).

    """

    def __init__(self, job_id: str, message: str) -> None:
        """Initialize SalesforceBulkJobError."""
        super().__init__(errors=[], status_code=0)
        self.job_id = job_id
        self.args = (f"Bulk job {job_id!r} failed: {message}",)


class BulkJobTimeoutError(SalesforceAPIError):
    """Raised when polling a Bulk API 2.0 job exceeds the configured timeout.

    Attributes:
        job_id: The Salesforce bulk job ID.
        max_wait: The ``max_wait`` value (in seconds) that was exceeded.
        errors: Always an empty list.
        status_code: Always ``0``.

    """

    def __init__(self, job_id: str, max_wait: float) -> None:
        """Initialize BulkJobTimeoutError."""
        super().__init__(errors=[], status_code=0)
        self.job_id = job_id
        self.max_wait = max_wait
        self.args = (f"Bulk job {job_id!r} timed out after {max_wait:.1f}s",)


class SalesforceMetadataDeployError(SalesforceAPIError):
    """Raised when a metadata deploy reaches a failed terminal status."""

    def __init__(self, deploy_id: str, status: str, message: str) -> None:
        """Initialize SalesforceMetadataDeployError."""
        super().__init__(errors=[], status_code=0)
        self.deploy_id = deploy_id
        self.status = status
        self.args = (
            f"Metadata deploy {deploy_id!r} ended with status {status!r}: {message}",
        )


class MetadataDeployTimeoutError(SalesforceAPIError):
    """Raised when metadata deploy polling exceeds the configured timeout."""

    def __init__(self, deploy_id: str, max_wait: float) -> None:
        """Initialize MetadataDeployTimeoutError."""
        super().__init__(errors=[], status_code=0)
        self.deploy_id = deploy_id
        self.max_wait = max_wait
        self.args = (f"Metadata deploy {deploy_id!r} timed out after {max_wait:.1f}s",)


# ---------------------------------------------------------------------------
# Error-code → exception-class mapping
# ---------------------------------------------------------------------------

_VALIDATION_CODES: frozenset[str] = frozenset(
    {
        "DATE_OUT_OF_RANGE",
        "ENTITY_SAVE_VALIDATION_ERROR",
        "FIELD_CUSTOM_VALIDATION_EXCEPTION",
        "FIELD_FILTER_VALIDATION_EXCEPTION",
        "FIELD_INTEGRITY_EXCEPTION",
        "INVALID_ARGUMENT_TYPE",
        "INVALID_FIELD",
        "INVALID_FIELD_FOR_INSERT_UPDATE",
        "INVALID_OR_NULL_FOR_RESTRICTED_PICKLIST",
        "INVALID_TEXT_REPRESENTATION",
        "INVALID_TYPE_ON_FIELD_IN_RECORD",
        "NUMBER_OUTSIDE_VALID_RANGE",
        "REQUIRED_FIELD_MISSING",
        "STRING_TOO_LONG",
    }
)

_DUPLICATE_CODES: frozenset[str] = frozenset(
    {
        "DUPLICATE_EXTERNAL_ID",
        "DUPLICATE_VALUE",
        "DUPLICATES_DETECTED",
    }
)

_NOT_FOUND_CODES: frozenset[str] = frozenset(
    {
        "ENTITY_IS_ARCHIVED",
        "ENTITY_IS_DELETED",
        "NOT_FOUND",
        "RECORD_NOT_FOUND",
        "SCHEMA_OBJECT_NOT_FOUND",
    }
)

_SESSION_EXPIRED_CODES: frozenset[str] = frozenset(
    {
        "INVALID_ACCESS_TOKEN",
        "INVALID_SESSION_ID",
        "NO_ACCESS_TOKEN",
        "REFRESH_FAILED",
        "SESSION_EXPIRED",
        "SESSION_INVALIDATED",
    }
)

_PERMISSION_CODES: frozenset[str] = frozenset(
    {
        "CANNOT_INSERT_UPDATE_ACTIVATE_ENTITY",
        "FORBIDDEN_EXCEPTION",
        "GUEST_INSUFFICIENT_ACCESS",
        "INSUFFICIENT_ACCESS",
        "INSUFFICIENT_ACCESS_ON_CROSS_REFERENCE_ENTITY",
        "INSUFFICIENT_ACCESS_OR_READONLY",
        "UNAUTHORIZED_EXCEPTION",
    }
)

_LOCK_CODES: frozenset[str] = frozenset(
    {
        "RECORD_LOCKED",
        "UNABLE_TO_LOCK_RECORD",
        "UNABLE_TO_LOCK_ROW",
    }
)

_ERROR_CODE_MAP: dict[str, type[SalesforceAPIError]] = {
    **dict.fromkeys(_VALIDATION_CODES, SalesforceValidationError),
    **dict.fromkeys(_DUPLICATE_CODES, SalesforceDuplicateError),
    **dict.fromkeys(_NOT_FOUND_CODES, SalesforceNotFoundError),
    **dict.fromkeys(_SESSION_EXPIRED_CODES, SalesforceSessionExpiredError),
    **dict.fromkeys(_PERMISSION_CODES, SalesforcePermissionError),
    **dict.fromkeys(_LOCK_CODES, SalesforceLockError),
}


# ---------------------------------------------------------------------------
# Public helper
# ---------------------------------------------------------------------------


def raise_for_salesforce_errors(response: Response) -> None:
    """Parse a Salesforce error response body and raise a typed exception.

    Attempts to parse the response body as a Salesforce REST API error list
    (``[{"errorCode": ..., "message": ..., "fields": [...]}]``).  If the
    body matches, raises the most specific ``SalesforceAPIError`` subclass for
    the first ``errorCode``.  If parsing fails or the body is not a valid
    Salesforce error list, returns silently so the caller can fall back to
    generic HTTP error handling.

    Raises:
        SalesforceAPIError: (or a typed subclass) when the body contains at
            least one valid Salesforce error object.

    """
    try:
        body = json.loads(response.content or b"")
    except (ValueError, TypeError):
        return

    if not isinstance(body, list) or not body:
        return

    try:
        errors = [SObjectError.model_validate(entry) for entry in body]
    except (ValidationError, TypeError, ValueError):
        return

    first_code = errors[0].error_code
    exc_cls = _ERROR_CODE_MAP.get(first_code, SalesforceAPIError)
    raise exc_cls(errors=errors, status_code=response.status_code)
