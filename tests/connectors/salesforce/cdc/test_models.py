"""Tests for Salesforce CDC models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from plynth.connectors.salesforce.cdc import (
    SalesforceCDCEnvelope,
    SalesforceCDCEvent,
    SalesforceCDCSubscribeRequest,
)


class TestSalesforceCDCSubscribeRequest:
    """Test suite for SalesforceCDCSubscribeRequest."""

    def test_validates_generic_subscription_fields(self) -> None:
        """Validate the request stores only generic CDC subscription data."""
        request = SalesforceCDCSubscribeRequest.model_validate(
            {"channel": "/data/AccountChangeEvent", "replay_id": 42}
        )

        assert request.channel == "/data/AccountChangeEvent"
        assert request.replay_id == 42

    def test_rejects_empty_channel(self) -> None:
        """Reject empty channel values."""
        with pytest.raises(ValidationError):
            SalesforceCDCSubscribeRequest.model_validate({"channel": ""})

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
                    "commit_number": 7,
                    "commit_timestamp": 1712345678,
                    "transaction_key": "tx-123",
                    "sequence_number": 1,
                },
                "payload": {"Id": "001xx000003GYWJAA4", "Name": "ACME"},
            }
        )

        assert event.channel == "/data/AccountChangeEvent"
        assert event.replay_id == 42
        assert event.envelope.object_name == "Account"
        assert event.envelope.event_type == "CREATE"
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
