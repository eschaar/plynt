"""Tests for Salesforce integration models."""

from __future__ import annotations

import pytest
from pydantic import Field, ValidationError

from plynth.connectors.salesforce.models import (
    SalesforceLimit,
    SalesforceLimitsResponse,
    SalesforceSearchRecord,
    SObjectCreateResult,
    SObjectError,
    SObjectPayload,
)


class TestSObjectError:
    """Tests for SObjectError."""

    def test_validates_from_salesforce_wire_names(self) -> None:
        """Validate validates from salesforce wire names."""
        err = SObjectError.model_validate(
            {
                "message": "Name required",
                "errorCode": "REQUIRED_FIELD_MISSING",
                "fields": ["Name"],
            }
        )
        assert err.message == "Name required"
        assert err.error_code == "REQUIRED_FIELD_MISSING"
        assert err.fields == ["Name"]

    def test_fields_defaults_to_empty_list(self) -> None:
        """Validate fields defaults to empty list."""
        err = SObjectError.model_validate(
            {"message": "Unknown error", "errorCode": "UNKNOWN_EXCEPTION"}
        )
        assert err.fields == []

    def test_can_construct_with_python_name(self) -> None:
        """Validate can construct with python name."""
        err = SObjectError(message="Oops", error_code="UNKNOWN_EXCEPTION")  # type: ignore[call-arg]
        assert err.error_code == "UNKNOWN_EXCEPTION"

    def test_invalid_missing_message_raises(self) -> None:
        """Validate invalid missing message raises."""
        with pytest.raises(ValidationError):
            SObjectError.model_validate({"errorCode": "UNKNOWN_EXCEPTION"})


class TestSObjectCreateResult:
    """Tests for SObjectCreateResult."""

    def test_validates_from_salesforce_response(self) -> None:
        """Validate validates from salesforce response."""
        result = SObjectCreateResult.model_validate(
            {"id": "001xx000003GYWJAA4", "success": True, "errors": []}
        )
        assert result.id == "001xx000003GYWJAA4"
        assert result.success is True
        assert result.errors == []

    def test_errors_defaults_to_empty_list(self) -> None:
        """Validate errors defaults to empty list."""
        result = SObjectCreateResult.model_validate(
            {"id": "001xx000003GYWJAA4", "success": True}
        )
        assert result.errors == []

    def test_parses_nested_errors(self) -> None:
        """Validate parses nested errors."""
        result = SObjectCreateResult.model_validate(
            {
                "id": "",
                "success": False,
                "errors": [
                    {
                        "message": "Name required",
                        "errorCode": "REQUIRED_FIELD_MISSING",
                        "fields": ["Name"],
                    }
                ],
            }
        )
        assert len(result.errors) == 1
        assert isinstance(result.errors[0], SObjectError)
        assert result.errors[0].error_code == "REQUIRED_FIELD_MISSING"

    def test_invalid_missing_id_raises(self) -> None:
        """Validate invalid missing id raises."""
        with pytest.raises(ValidationError):
            SObjectCreateResult.model_validate({"success": True, "errors": []})


class TestSObjectPayload:
    """Tests for SObjectPayload."""

    def test_to_payload_uses_serialization_alias(self) -> None:
        """Validate to payload uses serialization alias."""

        class AccountPayload(SObjectPayload):
            """Represent AccountPayload."""

            name: str = Field(serialization_alias="Name")
            account_number: str = Field(serialization_alias="AccountNumber")

        payload = AccountPayload(name="ACME Corp", account_number="ACC-001")
        result = payload.to_payload()
        assert result == {"Name": "ACME Corp", "AccountNumber": "ACC-001"}

    def test_to_payload_excludes_none_fields(self) -> None:
        """Validate to payload excludes none fields."""

        class AccountPayload(SObjectPayload):
            """Represent AccountPayload."""

            name: str = Field(serialization_alias="Name")
            phone: str | None = Field(default=None, serialization_alias="Phone")

        payload = AccountPayload(name="ACME Corp")
        result = payload.to_payload()
        assert result == {"Name": "ACME Corp"}
        assert "Phone" not in result

    def test_to_payload_includes_set_optional_fields(self) -> None:
        """Validate to payload includes set optional fields."""

        class AccountPayload(SObjectPayload):
            """Represent AccountPayload."""

            name: str = Field(serialization_alias="Name")
            phone: str | None = Field(default=None, serialization_alias="Phone")

        payload = AccountPayload(name="ACME Corp", phone="+31201234567")
        result = payload.to_payload()
        assert result == {"Name": "ACME Corp", "Phone": "+31201234567"}

    def test_to_payload_returns_dict(self) -> None:
        """Validate to payload returns dict."""

        class SimplePayload(SObjectPayload):
            """Represent SimplePayload."""

            value: str = Field(serialization_alias="Value__c")

        payload = SimplePayload(value="test")
        assert isinstance(payload.to_payload(), dict)


_LIMITS_PAYLOAD = {
    "DailyApiRequests": {"Max": 15000, "Remaining": 14999},
    "SingleEmail": {"Max": 5000, "Remaining": 5000},
}


class TestSalesforceSearchRecord:
    """Tests for SalesforceSearchRecord field access."""

    def _make(self, extra: dict[str, object] | None = None) -> SalesforceSearchRecord:
        """Handle make."""
        data: dict[str, object] = {
            "attributes": {
                "type": "Account",
                "url": "/services/data/v59.0/sobjects/Account/001",
            },
            "Id": "001000000000001",
        }
        if extra:
            data.update(extra)
        return SalesforceSearchRecord.model_validate(data)

    def test_id_via_getitem(self) -> None:
        """Validate id via getitem."""
        rec = self._make()
        assert rec["Id"] == "001000000000001"

    def test_extra_field_via_getitem(self) -> None:
        """Validate extra field via getitem."""
        rec = self._make({"Name": "Acme"})
        assert rec["Name"] == "Acme"

    def test_missing_extra_field_returns_none(self) -> None:
        """Validate missing extra field returns none."""
        rec = self._make()
        # model_extra is empty; missing key must return None, not raise.
        assert rec["NonExistent"] is None

    def test_sobject_type_property(self) -> None:
        """Validate sobject type property."""
        rec = self._make()
        assert rec.sobject_type == "Account"

    def test_sobject_type_falls_back_to_empty_string_when_missing(self) -> None:
        """Validate missing type metadata falls back to an empty string."""
        rec = SalesforceSearchRecord.model_validate(
            {
                "attributes": {
                    "url": "/services/data/v59.0/sobjects/Account/001",
                },
                "Id": "001000000000001",
            }
        )
        assert rec.sobject_type == ""


class TestSalesforceLimitsResponse:
    """Tests for SalesforceLimitsResponse mapping behaviour."""

    def _make(self) -> SalesforceLimitsResponse:
        """Handle make."""
        return SalesforceLimitsResponse.model_validate(_LIMITS_PAYLOAD)

    def test_item_access_by_key(self) -> None:
        """Validate item access by key."""
        limits = self._make()
        assert limits["DailyApiRequests"].remaining == 14999
        assert limits["DailyApiRequests"].max_value == 15000

    def test_keys_contains_all_names(self) -> None:
        """Validate keys contains all names."""
        limits = self._make()
        assert set(limits.keys()) == {"DailyApiRequests", "SingleEmail"}

    def test_len_matches_entry_count(self) -> None:
        """Validate len matches entry count."""
        limits = self._make()
        assert len(limits) == 2

    def test_items_returns_key_value_pairs(self) -> None:
        """Validate items returns key value pairs."""
        limits = self._make()
        pairs = dict(limits.items())
        assert isinstance(pairs["SingleEmail"], SalesforceLimit)
        assert pairs["SingleEmail"].max_value == 5000

    def test_values_returns_limit_objects(self) -> None:
        """Validate values returns limit objects."""
        limits = self._make()
        assert all(isinstance(v, SalesforceLimit) for v in limits.values())

    def test_keys_returns_salesforce_names(self) -> None:
        """Validate keys returns salesforce names."""
        limits = self._make()
        assert "DailyApiRequests" in limits.keys()

    def test_contains(self) -> None:
        """Validate contains."""
        limits = self._make()
        assert "DailyApiRequests" in limits
        assert "NonExistent" not in limits

    def test_model_dump_returns_plain_dict(self) -> None:
        """Validate model dump returns plain dict."""
        limits = self._make()
        data = limits.model_dump()
        assert data == {
            "DailyApiRequests": {"max_value": 15000, "remaining": 14999},
            "SingleEmail": {"max_value": 5000, "remaining": 5000},
        }

    def test_no_root_needed_in_for_loop(self) -> None:
        """Validate no root needed in for loop."""
        limits = self._make()
        names = [name for name, _ in sorted(limits.items())]
        assert names == ["DailyApiRequests", "SingleEmail"]
