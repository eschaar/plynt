"""Typed request, envelope, and auth models for Salesforce CDC.

These models represent the stable connector-facing contract that sits between
Salesforce Pub/Sub mechanics and downstream consumers. They intentionally model
generic CDC concepts only, without leaking tenant- or shadow-store-specific
concerns into the package surface.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "SalesforceCDCAuthMetadata",
    "SalesforceCDCEnvelope",
    "SalesforceCDCEvent",
    "SalesforceCDCSubscribeRequest",
]


class SalesforceCDCAuthMetadata(BaseModel):
    """Typed Salesforce Pub/Sub authentication metadata.

    Salesforce expects authentication values in gRPC metadata headers rather
    than in HTTP-style Authorization headers. This model keeps that mapping
    explicit and testable.
    """

    model_config = ConfigDict(extra="forbid")

    access_token: str = Field(min_length=1)
    instance_url: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)

    def to_metadata(self) -> dict[str, str]:
        """Return the gRPC metadata headers required by Salesforce Pub/Sub."""
        return {
            "accesstoken": self.access_token,
            "instanceurl": self.instance_url,
            "tenantid": self.tenant_id,
        }


class SalesforceCDCSubscribeRequest(BaseModel):
    """Describe a generic Salesforce CDC subscription request.

    The request stays intentionally small: channel selection, optional replay
    cursor, and flow-control volume. Higher-level replication or batching rules
    belong outside the connector.
    """

    model_config = ConfigDict(extra="forbid")

    channel: str = Field(min_length=1)
    replay_id: int | None = Field(default=None, ge=0)
    num_requested: int = Field(default=1, ge=1)


class SalesforceCDCEnvelope(BaseModel):
    """Represent common Salesforce CDC envelope metadata.

    The envelope mirrors the connector-safe subset of ``ChangeEventHeader`` and
    transport-side metadata, while leaving record field data in the event body.
    """

    model_config = ConfigDict(extra="forbid")

    channel: str = Field(min_length=1)
    object_name: str = Field(min_length=1)
    replay_id: int = Field(ge=0)
    event_type: str = Field(min_length=1)
    change_type: str = Field(min_length=1)
    record_ids: list[str] = Field(default_factory=list)
    schema_id: str | None = Field(default=None, min_length=1)
    change_origin: str | None = Field(default=None, min_length=1)
    commit_number: int | None = Field(default=None, ge=0)
    commit_timestamp: int | None = Field(default=None, ge=0)
    commit_user: str | None = Field(default=None, min_length=1)
    transaction_key: str | None = Field(default=None, min_length=1)
    sequence_number: int | None = Field(default=None, ge=0)
    changed_fields: list[str] = Field(default_factory=list)
    nulled_fields: list[str] = Field(default_factory=list)
    diff_fields: list[str] = Field(default_factory=list)


class SalesforceCDCEvent(BaseModel):
    """Represent a typed Salesforce CDC event.

    The event separates envelope metadata from payload fields so consumers can
    reason about replay, ordering, and merge semantics without parsing record
    values.
    """

    model_config = ConfigDict(extra="forbid")

    envelope: SalesforceCDCEnvelope
    payload: dict[str, Any] = Field(default_factory=dict)

    @property
    def channel(self) -> str:
        """Return the CDC channel."""
        return self.envelope.channel

    @property
    def replay_id(self) -> int:
        """Return the CDC replay cursor."""
        return self.envelope.replay_id
