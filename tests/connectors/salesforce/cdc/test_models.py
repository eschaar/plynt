"""Focused tests for Salesforce CDC request and envelope models.

These tests protect the connector-facing data contract: auth metadata headers,
subscribe request validation, and the generic CDC envelope shape shared across
standard and custom objects.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from plynt.connectors.salesforce.cdc import (
    SalesforceCDCAuthMetadata,
    SalesforceCDCEnvelope,
    SalesforceCDCEvent,
    SalesforceCDCSubscribeRequest,
)


class TestSalesforceCDCAuthMetadata:
    """Test suite for SalesforceCDCAuthMetadata."""

    def test_builds_salesforce_pubsub_metadata_headers(self) -> None:
        """Convert typed auth metadata into Salesforce header keys."""
        metadata = SalesforceCDCAuthMetadata(
            access_token="token-123",
            instance_url="https://example.my.salesforce.com",
            tenant_id="00Dxx0000000001",
        )

        assert metadata.to_metadata() == {
            "accesstoken": "token-123",
            "instanceurl": "https://example.my.salesforce.com",
            "tenantid": "00Dxx0000000001",
        }


class TestSalesforceCDCSubscribeRequest:
    """Test suite for SalesforceCDCSubscribeRequest."""

    def test_validates_generic_subscription_fields(self) -> None:
        """Validate the request stores only generic CDC subscription data."""
        request = SalesforceCDCSubscribeRequest.model_validate(
            {
                "channel": "/data/AccountChangeEvent",
                "replay_id": 42,
                "num_requested": 10,
            }
        )

        assert request.channel == "/data/AccountChangeEvent"
        assert request.replay_id == 42
        assert request.num_requested == 10

    def test_rejects_empty_channel(self) -> None:
        """Reject empty channel values."""
        with pytest.raises(ValidationError):
            SalesforceCDCSubscribeRequest.model_validate({"channel": ""})

    def test_rejects_non_positive_num_requested(self) -> None:
        """Reject invalid fetch request sizes."""
        with pytest.raises(ValidationError):
            SalesforceCDCSubscribeRequest.model_validate(
                {"channel": "/data/AccountChangeEvent", "num_requested": 0}
            )

    def test_does_not_define_instance_specific_fields(self) -> None:
        """Keep instance and tenant routing out of the generic request model."""
        field_names = set(SalesforceCDCSubscribeRequest.model_fields)

        assert "instance_url" not in field_names
        assert "tenant_id" not in field_names
        assert "customer_id" not in field_names


class TestSalesforceCDCEvent:
    """Test suite for SalesforceCDCEvent."""

    def test_validates_typed_event_envelope(self) -> None:
        """Validate a typed CDC envelope with generic payload data."""
        event = SalesforceCDCEvent.model_validate(
            {
                "envelope": {
                    "channel": "/data/AccountChangeEvent",
                    "object_name": "Account",
                    "replay_id": 42,
                    "event_type": "CREATE",
                    "change_type": "CREATE",
                    "record_ids": ["001xx000003GYWJAA4"],
                    "schema_id": "8f01f45e-6fe8-4f70-afce-9f2f549fd26b",
                    "change_origin": "com/salesforce/api/rest/67.0",
                    "commit_number": 7,
                    "commit_timestamp": 1712345678,
                    "commit_user": "005xx0000000001AAA",
                    "transaction_key": "tx-123",
                    "sequence_number": 1,
                    "changed_fields": ["Name"],
                    "nulled_fields": [],
                    "diff_fields": [],
                },
                "payload": {"Id": "001xx000003GYWJAA4", "Name": "ACME"},
            }
        )

        assert event.channel == "/data/AccountChangeEvent"
        assert event.replay_id == 42
        assert event.envelope.object_name == "Account"
        assert event.envelope.event_type == "CREATE"
        assert event.envelope.schema_id is not None
        assert event.envelope.record_ids == ["001xx000003GYWJAA4"]
        assert event.payload["Name"] == "ACME"

    def test_validates_custom_object_envelope(self) -> None:
        """Allow generic custom-object CDC envelopes."""
        event = SalesforceCDCEvent.model_validate(
            {
                "envelope": {
                    "channel": "/data/Contract__ChangeEvent",
                    "object_name": "Contract__c",
                    "replay_id": 9,
                    "event_type": "UPDATE",
                    "change_type": "UPDATE",
                },
                "payload": {"Id": "a01xx0000000001AAA"},
            }
        )

        assert event.envelope.object_name == "Contract__c"
        assert event.channel == "/data/Contract__ChangeEvent"

    def test_allows_merged_record_identifiers(self) -> None:
        """Allow merged CDC events containing multiple record identifiers."""
        event = SalesforceCDCEvent.model_validate(
            {
                "envelope": {
                    "channel": "/data/AccountChangeEvent",
                    "object_name": "Account",
                    "replay_id": 12,
                    "event_type": "UPDATE",
                    "change_type": "UPDATE",
                    "record_ids": [
                        "001xx000003GYWJAA4",
                        "001xx000003GYWJAA5",
                    ],
                },
                "payload": {"Industry": "Apparel"},
            }
        )

        assert len(event.envelope.record_ids) == 2

    def test_rejects_negative_commit_timestamp(self) -> None:
        """Reject negative commit timestamp values."""
        with pytest.raises(ValidationError):
            SalesforceCDCEvent.model_validate(
                {
                    "envelope": {
                        "channel": "/data/AccountChangeEvent",
                        "object_name": "Account",
                        "replay_id": 42,
                        "event_type": "UPDATE",
                        "change_type": "UPDATE",
                        "commit_timestamp": -1,
                    },
                }
            )

    def test_rejects_negative_replay_id(self) -> None:
        """Reject negative replay identifiers."""
        with pytest.raises(ValidationError):
            SalesforceCDCEvent.model_validate(
                {
                    "envelope": {
                        "channel": "/data/AccountChangeEvent",
                        "object_name": "Account",
                        "replay_id": -1,
                        "event_type": "CREATE",
                        "change_type": "CREATE",
                    }
                }
            )

    def test_does_not_define_instance_specific_fields(self) -> None:
        """Keep instance and tenant routing out of the generic event envelope."""
        field_names = set(SalesforceCDCEvent.model_fields)
        envelope_field_names = set(SalesforceCDCEnvelope.model_fields)

        assert "instance_url" not in field_names
        assert "tenant_id" not in field_names
        assert "customer_id" not in field_names
        assert "instance_url" not in envelope_field_names
        assert "tenant_id" not in envelope_field_names
        assert "customer_id" not in envelope_field_names
