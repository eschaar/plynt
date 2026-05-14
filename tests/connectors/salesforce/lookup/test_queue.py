"""Tests for Salesforce Queue lookup services."""

from __future__ import annotations

from typing import Any

from plynth.connectors.salesforce.lookup import (
    AsyncSalesforceQueueLookupService,
    SalesforceQueueLookupService,
)
from tests.connectors.salesforce.conftest import render_json_bytes
from tests.connectors.salesforce.lookup.conftest import (
    make_async_client,
    make_sync_client,
)


class TestSalesforceQueueLookupService:
    """Test sync Queue lookup behavior."""

    def test_list_builds_queue_query_with_filters(self) -> None:
        payload: dict[str, Any] = {"records": [{"Id": "00GA", "Name": "Support"}]}
        client, transport = make_sync_client(content=render_json_bytes(payload))
        service = SalesforceQueueLookupService(client)

        rows = service.list(name="Support", developer_name="Support_Queue")

        soql = transport.send.call_args[0][0].params.get("q", "")
        assert "FROM Group" in soql
        assert "Type = 'Queue'" in soql
        assert "Name = 'Support'" in soql
        assert "DeveloperName = 'Support_Queue'" in soql
        assert rows == payload["records"]

    def test_get_by_name_sets_limit(self) -> None:
        payload: dict[str, Any] = {"records": [{"Id": "00GA", "Name": "Support"}]}
        client, transport = make_sync_client(content=render_json_bytes(payload))
        service = SalesforceQueueLookupService(client)

        row = service.get_by_name("Support")

        soql = transport.send.call_args[0][0].params.get("q", "")
        assert "Type = 'Queue'" in soql
        assert "Name = 'Support'" in soql
        assert "LIMIT 1" in soql
        assert row == payload["records"][0]

    def test_get_by_developer_name_returns_row(self) -> None:
        payload: dict[str, Any] = {
            "records": [{"Id": "00GA", "DeveloperName": "Support_Queue"}]
        }
        client, transport = make_sync_client(content=render_json_bytes(payload))
        service = SalesforceQueueLookupService(client)

        row = service.get_by_developer_name("Support_Queue")

        soql = transport.send.call_args[0][0].params.get("q", "")
        assert "FROM Group" in soql
        assert "Type = 'Queue'" in soql
        assert "DeveloperName = 'Support_Queue'" in soql
        assert "LIMIT 1" in soql
        assert row == payload["records"][0]

    def test_get_by_developer_name_returns_none_when_empty(self) -> None:
        payload: dict[str, Any] = {"records": []}
        client, _ = make_sync_client(content=render_json_bytes(payload))
        service = SalesforceQueueLookupService(client)

        row = service.get_by_developer_name("Nonexistent")

        assert row is None


class TestAsyncSalesforceQueueLookupService:
    """Test async Queue lookup behavior."""

    async def test_async_queue_get_by_developer_name_returns_row(self) -> None:
        payload: dict[str, Any] = {"records": [{"Id": "00GA", "Name": "Support"}]}
        client, transport = make_async_client(content=render_json_bytes(payload))
        service = AsyncSalesforceQueueLookupService(client)

        row = await service.get_by_developer_name("Support_Queue")

        soql = transport.send.call_args[0][0].params.get("q", "")
        assert "Type = 'Queue'" in soql
        assert "DeveloperName = 'Support_Queue'" in soql
        assert "LIMIT 1" in soql
        assert row == payload["records"][0]

    async def test_async_list_returns_rows(self) -> None:
        payload: dict[str, Any] = {
            "records": [
                {"Id": "00GA", "Name": "Support", "DeveloperName": "Support_Queue"}
            ]
        }
        client, transport = make_async_client(content=render_json_bytes(payload))
        service = AsyncSalesforceQueueLookupService(client)

        rows = await service.list(name="Support", developer_name="Support_Queue")

        soql = transport.send.call_args[0][0].params.get("q", "")
        assert "FROM Group" in soql
        assert "Type = 'Queue'" in soql
        assert "Name = 'Support'" in soql
        assert "DeveloperName = 'Support_Queue'" in soql
        assert rows == payload["records"]

    async def test_async_get_by_name_returns_row(self) -> None:
        payload: dict[str, Any] = {"records": [{"Id": "00GA", "Name": "Billing"}]}
        client, transport = make_async_client(content=render_json_bytes(payload))
        service = AsyncSalesforceQueueLookupService(client)

        row = await service.get_by_name("Billing")

        soql = transport.send.call_args[0][0].params.get("q", "")
        assert "Type = 'Queue'" in soql
        assert "Name = 'Billing'" in soql
        assert "LIMIT 1" in soql
        assert row == payload["records"][0]

    async def test_async_get_by_name_returns_none_when_empty(self) -> None:
        payload: dict[str, Any] = {"records": []}
        client, _ = make_async_client(content=render_json_bytes(payload))
        service = AsyncSalesforceQueueLookupService(client)

        row = await service.get_by_name("Nonexistent")

        assert row is None
