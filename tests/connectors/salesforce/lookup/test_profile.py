"""Tests for Salesforce Profile lookup services."""

from __future__ import annotations

from typing import Any

from plynth.connectors.salesforce.lookup import (
    AsyncSalesforceProfileLookupService,
    SalesforceProfileLookupService,
)
from tests.connectors.salesforce.conftest import render_json_bytes
from tests.connectors.salesforce.lookup.conftest import (
    make_async_client,
    make_sync_client,
)


class TestSalesforceProfileLookupService:
    """Test sync Profile lookup behavior."""

    def test_list_builds_profile_query_with_filters(self) -> None:
        payload: dict[str, Any] = {"records": [{"Id": "00eA", "Name": "Standard User"}]}
        client, transport = make_sync_client(content=render_json_bytes(payload))
        service = SalesforceProfileLookupService(client)

        rows = service.list(
            name="Standard User",
            developer_name="Standard",
            user_type="Standard",
        )

        soql = transport.send.call_args[0][0].params.get("q", "")
        assert "FROM Profile" in soql
        assert "Name = 'Standard User'" in soql
        assert "DeveloperName = 'Standard'" in soql
        assert "UserType = 'Standard'" in soql
        assert rows == payload["records"]

    def test_get_by_developer_name_sets_limit(self) -> None:
        payload: dict[str, Any] = {
            "records": [{"Id": "00eA", "DeveloperName": "Standard"}]
        }
        client, transport = make_sync_client(content=render_json_bytes(payload))
        service = SalesforceProfileLookupService(client)

        row = service.get_by_developer_name("Standard")

        soql = transport.send.call_args[0][0].params.get("q", "")
        assert "DeveloperName = 'Standard'" in soql
        assert "LIMIT 1" in soql
        assert row == payload["records"][0]


class TestAsyncSalesforceProfileLookupService:
    """Test async Profile lookup behavior."""

    async def test_async_profile_get_by_name_returns_row(self) -> None:
        payload: dict[str, Any] = {"records": [{"Id": "00eA", "Name": "Standard User"}]}
        client, transport = make_async_client(content=render_json_bytes(payload))
        service = AsyncSalesforceProfileLookupService(client)

        row = await service.get_by_name("Standard User")

        soql = transport.send.call_args[0][0].params.get("q", "")
        assert "Name = 'Standard User'" in soql
        assert "LIMIT 1" in soql
        assert row == payload["records"][0]
