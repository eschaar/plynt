"""Generic Salesforce CDC primitives for Plynth."""

from __future__ import annotations

from plynth.connectors.salesforce.cdc.auth import AsyncSalesforceCDCAuthMetadataProvider
from plynth.connectors.salesforce.cdc.avro import (
    AvroPayloadDecoder,
    ensure_fastavro_runtime,
)
from plynth.connectors.salesforce.cdc.checkpoint import (
    CacheSalesforceCDCCheckpointStore,
    InMemorySalesforceCDCCheckpointStore,
    SalesforceCDCCheckpointStore,
)
from plynth.connectors.salesforce.cdc.models import (
    SalesforceCDCAuthMetadata,
    SalesforceCDCEnvelope,
    SalesforceCDCEvent,
    SalesforceCDCSubscribeRequest,
)
from plynth.connectors.salesforce.cdc.pubsub import (
    GrpcMethodPubSubAdapter,
    GrpcStubPubSubAdapter,
    SalesforcePubSubAdapter,
)
from plynth.connectors.salesforce.cdc.service import (
    AsyncSalesforceCDCSubscriber,
    SalesforceCDCGapError,
    SalesforceCDCOverflowError,
)

__all__ = [
    "AsyncSalesforceCDCAuthMetadataProvider",
    "AsyncSalesforceCDCSubscriber",
    "AvroPayloadDecoder",
    "CacheSalesforceCDCCheckpointStore",
    "GrpcMethodPubSubAdapter",
    "GrpcStubPubSubAdapter",
    "InMemorySalesforceCDCCheckpointStore",
    "SalesforceCDCAuthMetadata",
    "SalesforceCDCCheckpointStore",
    "SalesforceCDCEnvelope",
    "SalesforceCDCEvent",
    "SalesforceCDCGapError",
    "SalesforceCDCOverflowError",
    "SalesforceCDCSubscribeRequest",
    "SalesforcePubSubAdapter",
    "ensure_fastavro_runtime",
]
