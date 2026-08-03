"""Generic Salesforce CDC primitives for Plynth."""

from __future__ import annotations

from plynth.connectors.salesforce.cdc.models import (
    SalesforceCDCAuthMetadata,
    SalesforceCDCEnvelope,
    SalesforceCDCEvent,
    SalesforceCDCSubscribeRequest,
)
from plynth.connectors.salesforce.cdc.service import (
    AsyncSalesforceCDCSubscriber,
)

__all__ = [
    "AsyncSalesforceCDCSubscriber",
    "SalesforceCDCAuthMetadata",
    "SalesforceCDCEnvelope",
    "SalesforceCDCEvent",
    "SalesforceCDCSubscribeRequest",
]
