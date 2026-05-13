"""Lookup service factories and registry mappings."""

from __future__ import annotations

from plynth.connectors.salesforce.lookup.pricebook import (
    AsyncSalesforcePricebookLookupService,
    SalesforcePricebookLookupService,
)
from plynth.connectors.salesforce.lookup.profile import (
    AsyncSalesforceProfileLookupService,
    SalesforceProfileLookupService,
)
from plynth.connectors.salesforce.lookup.queue import (
    AsyncSalesforceQueueLookupService,
    SalesforceQueueLookupService,
)
from plynth.connectors.salesforce.lookup.record_type import (
    AsyncSalesforceRecordTypeLookupService,
    SalesforceRecordTypeLookupService,
)
from plynth.connectors.salesforce.lookup.types import LookupType
from plynth.connectors.salesforce.lookup.user import (
    AsyncSalesforceUserLookupService,
    SalesforceUserLookupService,
)
from plynth.http.client import APIClient, AsyncAPIClient
from plynth.http.renderer import Renderer

SyncLookupService = (
    SalesforceRecordTypeLookupService
    | SalesforceUserLookupService
    | SalesforcePricebookLookupService
    | SalesforceQueueLookupService
    | SalesforceProfileLookupService
)
AsyncLookupService = (
    AsyncSalesforceRecordTypeLookupService
    | AsyncSalesforceUserLookupService
    | AsyncSalesforcePricebookLookupService
    | AsyncSalesforceQueueLookupService
    | AsyncSalesforceProfileLookupService
)

_SYNC_LOOKUP_SERVICE_MAP: dict[LookupType, type[SyncLookupService]] = {
    LookupType.RECORD_TYPE: SalesforceRecordTypeLookupService,
    LookupType.USER: SalesforceUserLookupService,
    LookupType.PRICEBOOK: SalesforcePricebookLookupService,
    LookupType.QUEUE: SalesforceQueueLookupService,
    LookupType.PROFILE: SalesforceProfileLookupService,
}

_ASYNC_LOOKUP_SERVICE_MAP: dict[LookupType, type[AsyncLookupService]] = {
    LookupType.RECORD_TYPE: AsyncSalesforceRecordTypeLookupService,
    LookupType.USER: AsyncSalesforceUserLookupService,
    LookupType.PRICEBOOK: AsyncSalesforcePricebookLookupService,
    LookupType.QUEUE: AsyncSalesforceQueueLookupService,
    LookupType.PROFILE: AsyncSalesforceProfileLookupService,
}


def create_sync_lookup_service(
    client: APIClient,
    kind: LookupType,
    *,
    api_version: str | None = None,
    renderer: Renderer | None = None,
) -> SyncLookupService:
    """Create a sync lookup service for the given lookup type."""
    service_cls = _SYNC_LOOKUP_SERVICE_MAP[kind]
    return service_cls(
        client,
        api_version=api_version,
        renderer=renderer,
    )


def create_async_lookup_service(
    client: AsyncAPIClient,
    kind: LookupType,
    *,
    api_version: str | None = None,
    renderer: Renderer | None = None,
) -> AsyncLookupService:
    """Create an async lookup service for the given lookup type."""
    service_cls = _ASYNC_LOOKUP_SERVICE_MAP[kind]
    return service_cls(
        client,
        api_version=api_version,
        renderer=renderer,
    )
