"""Salesforce lookup convenience services.

This module centralizes lookup-oriented DX helpers for common Salesforce
identifier resolution patterns.

Rule for adding new lookup conveniences:
- Only add a lookup convenience when the pattern is high-frequency,
  repeatable, and non-domain-specific.
- Keep lookup services as thin wrappers over the generic query/client layer.
- Do not place business logic in lookup services.
"""

from __future__ import annotations

from plynt.connectors.salesforce.lookup.base import (
    AsyncSalesforceLookupService,
    SalesforceLookupService,
)
from plynt.connectors.salesforce.lookup.factory import (
    AsyncLookupService,
    SyncLookupService,
    create_async_lookup_service,
    create_sync_lookup_service,
)
from plynt.connectors.salesforce.lookup.pricebook import (
    AsyncSalesforcePricebookLookupService,
    SalesforcePricebookLookupService,
)
from plynt.connectors.salesforce.lookup.profile import (
    AsyncSalesforceProfileLookupService,
    SalesforceProfileLookupService,
)
from plynt.connectors.salesforce.lookup.queue import (
    AsyncSalesforceQueueLookupService,
    SalesforceQueueLookupService,
)
from plynt.connectors.salesforce.lookup.record_type import (
    AsyncSalesforceRecordTypeLookupService,
    SalesforceRecordTypeLookupService,
)
from plynt.connectors.salesforce.lookup.types import LookupType
from plynt.connectors.salesforce.lookup.user import (
    AsyncSalesforceUserLookupService,
    SalesforceUserLookupService,
)

__all__ = [
    "AsyncLookupService",
    "AsyncSalesforceLookupService",
    "AsyncSalesforcePricebookLookupService",
    "AsyncSalesforceProfileLookupService",
    "AsyncSalesforceQueueLookupService",
    "AsyncSalesforceRecordTypeLookupService",
    "AsyncSalesforceUserLookupService",
    "LookupType",
    "SalesforceLookupService",
    "SalesforcePricebookLookupService",
    "SalesforceProfileLookupService",
    "SalesforceQueueLookupService",
    "SalesforceRecordTypeLookupService",
    "SalesforceUserLookupService",
    "SyncLookupService",
    "create_async_lookup_service",
    "create_sync_lookup_service",
]
