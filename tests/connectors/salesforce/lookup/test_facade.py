"""Tests for Salesforce facade lookup service factory wiring."""

from __future__ import annotations

from plynth.connectors.salesforce.facade import (
    AsyncSalesforceAPIFacade,
    LookupType,
    SalesforceAPIFacade,
)
from plynth.connectors.salesforce.lookup import (
    AsyncSalesforcePricebookLookupService,
    AsyncSalesforceProfileLookupService,
    AsyncSalesforceQueueLookupService,
    AsyncSalesforceRecordTypeLookupService,
    AsyncSalesforceUserLookupService,
    SalesforcePricebookLookupService,
    SalesforceProfileLookupService,
    SalesforceQueueLookupService,
    SalesforceRecordTypeLookupService,
    SalesforceUserLookupService,
)
from tests.connectors.salesforce.lookup.conftest import (
    make_async_client,
    make_sync_client,
)


class TestLookupFacadeWiring:
    """Test facade lookup returns expected lookup services by kind."""

    def test_sync_facade_lookup_returns_lookup_services_by_kind(self) -> None:
        client, _ = make_sync_client(content=b"{}")
        facade = SalesforceAPIFacade(client)

        assert isinstance(
            facade.lookup(LookupType.RECORD_TYPE),
            SalesforceRecordTypeLookupService,
        )
        assert isinstance(facade.lookup(LookupType.USER), SalesforceUserLookupService)
        assert isinstance(
            facade.lookup(LookupType.PRICEBOOK),
            SalesforcePricebookLookupService,
        )
        assert isinstance(facade.lookup(LookupType.QUEUE), SalesforceQueueLookupService)
        assert isinstance(
            facade.lookup(LookupType.PROFILE),
            SalesforceProfileLookupService,
        )

    def test_async_facade_lookup_returns_lookup_services_by_kind(self) -> None:
        client, _ = make_async_client(content=b"{}")
        facade = AsyncSalesforceAPIFacade(client)

        assert isinstance(
            facade.lookup(LookupType.RECORD_TYPE),
            AsyncSalesforceRecordTypeLookupService,
        )
        assert isinstance(
            facade.lookup(LookupType.USER),
            AsyncSalesforceUserLookupService,
        )
        assert isinstance(
            facade.lookup(LookupType.PRICEBOOK),
            AsyncSalesforcePricebookLookupService,
        )
        assert isinstance(
            facade.lookup(LookupType.QUEUE),
            AsyncSalesforceQueueLookupService,
        )
        assert isinstance(
            facade.lookup(LookupType.PROFILE),
            AsyncSalesforceProfileLookupService,
        )
