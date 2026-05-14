"""Tests for Salesforce typed error mapping."""

from __future__ import annotations

from typing import Any, TypedDict

import pytest

from plynth.base.response import Response
from plynth.connectors.salesforce.errors import (
    SalesforceAPIError,
    SalesforceDuplicateError,
    SalesforceInvalidFieldQueryError,
    SalesforceInvalidTypeQueryError,
    SalesforceLockError,
    SalesforceMalformedQueryError,
    SalesforceNotFoundError,
    SalesforcePermissionError,
    SalesforceSessionExpiredError,
    SalesforceValidationError,
    raise_for_salesforce_errors,
)
from plynth.http.renderer import JSONRenderer

_JSON_RENDERER = JSONRenderer()


def _json_bytes(data: Any) -> bytes:
    """Render test payloads to JSON bytes via the shared renderer layer."""
    return _JSON_RENDERER.render(data)


def _resp(body: object, status: int = 400) -> Response:
    """Build a Response with a JSON body."""
    return Response(status_code=status, content=_json_bytes(body))


class _SalesforceErrorPayload(TypedDict):
    """Represent SalesforceErrorPayload."""

    errorCode: str
    message: str
    fields: list[str]


def _sf_error(
    code: str,
    message: str = "msg",
    fields: list[str] | None = None,
) -> _SalesforceErrorPayload:
    """Handle sf error."""
    return {"errorCode": code, "message": message, "fields": fields or []}


class TestRaiseForSalesforceErrorsDoesNotRaise:
    """Test suite for RaiseForSalesforceErrorsDoesNotRaise."""

    @pytest.mark.parametrize(
        ("response",),
        [
            pytest.param(Response(status_code=400, content=b"not json"), id="non_json"),
            pytest.param(Response(status_code=400, content=b""), id="empty_body"),
            pytest.param(_resp(None), id="null_json"),
            pytest.param(
                _resp({"errorCode": "X", "message": "y"}),
                id="json_object_not_list",
            ),
            pytest.param(_resp([]), id="empty_json_list"),
            pytest.param(_resp([{"message": "oops"}]), id="missing_error_code"),
            pytest.param(_resp(["REQUIRED_FIELD_MISSING"]), id="list_non_objects"),
        ],
    )
    def test_invalid_or_non_salesforce_bodies(self, response: Response) -> None:
        """Invalid/unexpected bodies should not raise Salesforce exceptions."""
        raise_for_salesforce_errors(response)


class TestRaiseForSalesforceErrorsTypedExceptions:
    """Test suite for RaiseForSalesforceErrorsTypedExceptions."""

    @pytest.mark.parametrize(
        ("code", "expected"),
        [
            pytest.param(
                "MALFORMED_QUERY",
                SalesforceMalformedQueryError,
                id="malformed_query",
            ),
            pytest.param(
                "INVALID_TYPE",
                SalesforceInvalidTypeQueryError,
                id="invalid_type",
            ),
            pytest.param(
                "INVALID_FIELD",
                SalesforceInvalidFieldQueryError,
                id="invalid_field",
            ),
        ],
    )
    def test_query_codes(
        self,
        code: str,
        expected: type[SalesforceAPIError],
    ) -> None:
        """Validate query-specific error codes raise typed exceptions."""
        with pytest.raises(expected):
            raise_for_salesforce_errors(_resp([_sf_error(code)]))

    @pytest.mark.parametrize(
        ("code",),
        [
            pytest.param("REQUIRED_FIELD_MISSING", id="required_field_missing"),
            pytest.param(
                "FIELD_CUSTOM_VALIDATION_EXCEPTION",
                id="field_custom_validation_exception",
            ),
            pytest.param("STRING_TOO_LONG", id="string_too_long"),
            pytest.param(
                "INVALID_OR_NULL_FOR_RESTRICTED_PICKLIST",
                id="restricted_picklist",
            ),
        ],
    )
    def test_validation_codes(self, code: str) -> None:
        """Validate validation codes."""
        with pytest.raises(SalesforceValidationError):
            raise_for_salesforce_errors(_resp([_sf_error(code)]))

    @pytest.mark.parametrize(
        ("code",),
        [
            pytest.param("DUPLICATE_VALUE", id="duplicate_value"),
            pytest.param("DUPLICATES_DETECTED", id="duplicates_detected"),
            pytest.param("DUPLICATE_EXTERNAL_ID", id="duplicate_external_id"),
        ],
    )
    def test_duplicate_codes(self, code: str) -> None:
        """Validate duplicate codes."""
        with pytest.raises(SalesforceDuplicateError):
            raise_for_salesforce_errors(_resp([_sf_error(code)]))

    @pytest.mark.parametrize(
        ("code",),
        [
            pytest.param("ENTITY_IS_DELETED", id="entity_is_deleted"),
            pytest.param("ENTITY_IS_ARCHIVED", id="entity_is_archived"),
            pytest.param("RECORD_NOT_FOUND", id="record_not_found"),
            pytest.param("NOT_FOUND", id="not_found"),
            pytest.param("SCHEMA_OBJECT_NOT_FOUND", id="schema_object_not_found"),
        ],
    )
    def test_not_found_codes(self, code: str) -> None:
        """Validate not found codes."""
        with pytest.raises(SalesforceNotFoundError):
            raise_for_salesforce_errors(_resp([_sf_error(code)]))

    @pytest.mark.parametrize(
        ("code",),
        [
            pytest.param("INVALID_SESSION_ID", id="invalid_session_id"),
            pytest.param("SESSION_EXPIRED", id="session_expired"),
            pytest.param("INVALID_ACCESS_TOKEN", id="invalid_access_token"),
        ],
    )
    def test_session_expired_codes(self, code: str) -> None:
        """Validate session expired codes."""
        with pytest.raises(SalesforceSessionExpiredError):
            raise_for_salesforce_errors(_resp([_sf_error(code)], status=401))

    @pytest.mark.parametrize(
        ("code",),
        [
            pytest.param("INSUFFICIENT_ACCESS", id="insufficient_access"),
            pytest.param("FORBIDDEN_EXCEPTION", id="forbidden_exception"),
            pytest.param("UNAUTHORIZED_EXCEPTION", id="unauthorized_exception"),
        ],
    )
    def test_permission_codes(self, code: str) -> None:
        """Validate permission codes."""
        with pytest.raises(SalesforcePermissionError):
            raise_for_salesforce_errors(_resp([_sf_error(code)], status=403))

    @pytest.mark.parametrize(
        ("code", "status"),
        [
            pytest.param("UNABLE_TO_LOCK_RECORD", 503, id="unable_to_lock_record"),
            pytest.param("RECORD_LOCKED", 400, id="record_locked"),
        ],
    )
    def test_lock_codes(self, code: str, status: int) -> None:
        """Validate lock codes."""
        with pytest.raises(SalesforceLockError):
            raise_for_salesforce_errors(_resp([_sf_error(code)], status=status))

    # --- unknown → base ---

    def test_unknown_code_raises_base(self) -> None:
        """Validate unknown code raises base."""
        with pytest.raises(SalesforceAPIError) as exc_info:
            raise_for_salesforce_errors(_resp([_sf_error("SOME_EXOTIC_CODE")]))
        assert type(exc_info.value) is SalesforceAPIError

    # --- subtypes are SalesforceAPIError ---

    def test_validation_is_subclass(self) -> None:
        """Validate validation is subclass."""
        with pytest.raises(SalesforceAPIError):
            raise_for_salesforce_errors(_resp([_sf_error("REQUIRED_FIELD_MISSING")]))

    def test_duplicate_is_subclass(self) -> None:
        """Validate duplicate is subclass."""
        with pytest.raises(SalesforceAPIError):
            raise_for_salesforce_errors(_resp([_sf_error("DUPLICATE_VALUE")]))


class TestSalesforceAPIErrorAttributes:
    """Test suite for SalesforceAPIErrorAttributes."""

    def test_errors_list_populated(self) -> None:
        """Validate errors list populated."""
        with pytest.raises(SalesforceValidationError) as exc_info:
            raise_for_salesforce_errors(
                _resp(
                    [_sf_error("REQUIRED_FIELD_MISSING", "Name is required", ["Name"])]
                )
            )
        exc = exc_info.value
        assert len(exc.errors) == 1
        assert exc.errors[0].error_code == "REQUIRED_FIELD_MISSING"
        assert exc.errors[0].message == "Name is required"
        assert exc.errors[0].fields == ["Name"]

    def test_status_code_set(self) -> None:
        """Validate status code set."""
        with pytest.raises(SalesforceValidationError) as exc_info:
            raise_for_salesforce_errors(
                _resp([_sf_error("REQUIRED_FIELD_MISSING")], status=400)
            )
        assert exc_info.value.status_code == 400

    def test_str_includes_code_and_message(self) -> None:
        """Validate str includes code and message."""
        with pytest.raises(SalesforceAPIError) as exc_info:
            raise_for_salesforce_errors(
                _resp([_sf_error("REQUIRED_FIELD_MISSING", "Name is required")])
            )
        assert "REQUIRED_FIELD_MISSING" in str(exc_info.value)
        assert "Name is required" in str(exc_info.value)

    def test_multiple_errors_all_parsed(self) -> None:
        """Validate multiple errors all parsed."""
        body = [
            _sf_error("REQUIRED_FIELD_MISSING", "Name missing", ["Name"]),
            _sf_error("STRING_TOO_LONG", "Email too long", ["Email__c"]),
        ]
        with pytest.raises(SalesforceValidationError) as exc_info:
            raise_for_salesforce_errors(_resp(body))
        assert len(exc_info.value.errors) == 2

    def test_classification_by_first_error_code(self) -> None:
        # First code is DUPLICATE_VALUE → SalesforceDuplicateError, even though
        # second code would be classified differently.
        """Validate classification by first error code."""
        body = [
            _sf_error("DUPLICATE_VALUE", "Duplicate"),
            _sf_error("REQUIRED_FIELD_MISSING", "Missing"),
        ]
        with pytest.raises(SalesforceDuplicateError):
            raise_for_salesforce_errors(_resp(body))
