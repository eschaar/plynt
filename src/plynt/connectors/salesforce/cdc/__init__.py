"""Generic Salesforce CDC primitives for Plynt."""

from __future__ import annotations

from plynt.connectors.salesforce.cdc.auth import AsyncSalesforceCDCAuthMetadataProvider
from plynt.connectors.salesforce.cdc.avro import (
    AvroPayloadDecoder,
    ensure_fastavro_runtime,
)
from plynt.connectors.salesforce.cdc.checkpoint import (
    CacheSalesforceCDCCheckpointStore,
    InMemorySalesforceCDCCheckpointStore,
    SalesforceCDCCheckpointStore,
)
from plynt.connectors.salesforce.cdc.errors import (
    SalesforceCDCGapError,
    SalesforceCDCOverflowError,
    SalesforceCDCReplayInvalidError,
)
from plynt.connectors.salesforce.cdc.models import (
    SalesforceCDCAuthMetadata,
    SalesforceCDCEnvelope,
    SalesforceCDCEvent,
    SalesforceCDCSubscribeRequest,
)
from plynt.connectors.salesforce.cdc.pubsub import (
    GrpcMethodPubSubAdapter,
    GrpcStubPubSubAdapter,
    SalesforcePubSubAdapter,
    create_vendored_pubsub_adapter,
)
from plynt.connectors.salesforce.cdc.service import AsyncSalesforceCDCSubscriber

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
    "SalesforceCDCReplayInvalidError",
    "SalesforceCDCSubscribeRequest",
    "SalesforcePubSubAdapter",
    "create_vendored_pubsub_adapter",
    "ensure_fastavro_runtime",
]
