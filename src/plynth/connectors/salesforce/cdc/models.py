"""Generic Salesforce CDC request and event models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "SalesforceCDCEnvelope",
    "SalesforceCDCEvent",
    "SalesforceCDCSubscribeRequest",
]


class SalesforceCDCSubscribeRequest(BaseModel):
    """Describe a generic Salesforce CDC subscription request."""

    model_config = ConfigDict(extra="forbid")

    channel: str = Field(min_length=1)
    replay_id: int | None = Field(default=None, ge=0)


class SalesforceCDCEnvelope(BaseModel):
    """Represent common Salesforce CDC envelope metadata."""

    model_config = ConfigDict(extra="forbid")

    channel: str = Field(min_length=1)
    object_name: str = Field(min_length=1)
    replay_id: int = Field(ge=0)
    event_type: str = Field(min_length=1)
    change_type: str = Field(min_length=1)
    commit_number: int | None = Field(default=None, ge=0)
    commit_timestamp: int | None = Field(default=None, ge=0)
    transaction_key: str | None = Field(default=None, min_length=1)
    sequence_number: int | None = Field(default=None, ge=0)


class SalesforceCDCEvent(BaseModel):
    """Represent a typed Salesforce CDC envelope."""

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
