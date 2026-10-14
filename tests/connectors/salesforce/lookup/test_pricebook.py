"""Tests for Salesforce Pricebook lookup services."""

from __future__ import annotations

from typing import Any

from plynt.connectors.salesforce.lookup import (
    AsyncSalesforcePricebookLookupService,
    SalesforcePricebookLookupService,
)
from tests.connectors.salesforce.conftest import render_json_bytes
from tests.connectors.salesforce.lookup.conftest import (
    make_async_client,
    make_sync_client,
)


class TestSalesforcePricebookLookupService:
    """Test sync Pricebook lookup behavior."""

    def test_list_builds_pricebook_query_with_filters(self) -> None:
        payload: dict[str, Any] = {"records": [{"Id": "01sA", "Name": "Standard"}]}
        client, transport = make_sync_client(content=render_json_bytes(payload))
        service = SalesforcePricebookLookupService(client)

        rows = service.list(
            name="Standard",
            is_standard=True,
            is_active=True,
            currency_iso_code="EUR",
        )

        soql = transport.send.call_args[0][0].params.get("q", "")
        assert "FROM Pricebook2" in soql
        assert "Name = 'Standard'" in soql
        assert "IsStandard = true" in soql
        assert "IsActive = true" in soql
        assert "CurrencyIsoCode = 'EUR'" in soql
        assert rows == payload["records"]

    def test_get_standard_sets_required_filter_and_limit(self) -> None:
        payload: dict[str, Any] = {"records": [{"Id": "01sA", "IsStandard": True}]}
        client, transport = make_sync_client(content=render_json_bytes(payload))
        service = SalesforcePricebookLookupService(client)

        row = service.get_standard(is_active=True)

        soql = transport.send.call_args[0][0].params.get("q", "")
        assert "IsStandard = true" in soql
        assert "IsActive = true" in soql
        assert "LIMIT 1" in soql
        assert row == payload["records"][0]


class TestAsyncSalesforcePricebookLookupService:
    """Test async Pricebook lookup behavior."""

    async def test_async_pricebook_get_standard_returns_none_when_missing(self) -> None:
        client, _ = make_async_client(content=render_json_bytes({"records": []}))
        service = AsyncSalesforcePricebookLookupService(client)

        row = await service.get_standard(is_active=True)

        assert row is None

    async def test_async_pricebook_list_builds_query_with_filters(self) -> None:
        payload: dict[str, Any] = {"records": [{"Id": "01sA", "Name": "Standard"}]}
        client, transport = make_async_client(content=render_json_bytes(payload))
        service = AsyncSalesforcePricebookLookupService(client)

        rows = await service.list(
            name="Standard",
            is_standard=True,
            is_active=True,
            currency_iso_code="EUR",
        )

        soql = transport.send.call_args[0][0].params.get("q", "")
        assert "FROM Pricebook2" in soql
        assert "Name = 'Standard'" in soql
        assert "IsStandard = true" in soql
        assert "IsActive = true" in soql
        assert "CurrencyIsoCode = 'EUR'" in soql
        assert rows == payload["records"]
