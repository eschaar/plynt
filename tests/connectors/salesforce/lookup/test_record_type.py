"""Tests for Salesforce RecordType lookup services."""

from __future__ import annotations

from typing import Any

from plynt.connectors.salesforce.lookup import (
    AsyncSalesforceRecordTypeLookupService,
    SalesforceRecordTypeLookupService,
)
from tests.connectors.salesforce.conftest import render_json_bytes
from tests.connectors.salesforce.lookup.conftest import (
    make_async_client,
    make_sync_client,
)


class TestSalesforceRecordTypeLookupService:
    """Test sync RecordType lookup behavior."""

    def test_list_builds_filtered_record_type_query(self) -> None:
        payload: dict[str, Any] = {
            "records": [{"Id": "012A", "DeveloperName": "Business"}]
        }
        client, transport = make_sync_client(content=render_json_bytes(payload))
        service = SalesforceRecordTypeLookupService(client)

        rows = service.list(
            "Account",
            developer_name="Business",
            name="Business Account",
            is_active=True,
        )

        sent = transport.send.call_args[0][0]
        soql = sent.params.get("q", "")
        assert sent.url.endswith("/services/data/v59.0/query")
        assert "FROM RecordType" in soql
        assert "SobjectType = 'Account'" in soql
        assert "DeveloperName = 'Business'" in soql
        assert "Name = 'Business Account'" in soql
        assert "IsActive = true" in soql
        assert rows == payload["records"]

    def test_list_returns_empty_on_non_dict_payload(self) -> None:
        client, _ = make_sync_client(content=render_json_bytes([1, 2, 3]))
        service = SalesforceRecordTypeLookupService(client)

        rows = service.list("Account")

        assert rows == []

    def test_list_returns_empty_on_non_list_records(self) -> None:
        client, _ = make_sync_client(
            content=render_json_bytes({"records": {"Id": "012A"}})
        )
        service = SalesforceRecordTypeLookupService(client)

        rows = service.list("Account")

        assert rows == []

    def test_get_by_developer_name_returns_first_row(self) -> None:
        payload: dict[str, Any] = {"records": [{"Id": "012A"}, {"Id": "012B"}]}
        client, transport = make_sync_client(content=render_json_bytes(payload))
        service = SalesforceRecordTypeLookupService(client)

        row = service.get_by_developer_name("Account", "Business")

        soql = transport.send.call_args[0][0].params.get("q", "")
        assert "LIMIT 1" in soql
        assert row == payload["records"][0]


class TestAsyncSalesforceRecordTypeLookupService:
    """Test async RecordType lookup behavior."""

    async def test_async_record_type_list_uses_filters(self) -> None:
        payload: dict[str, Any] = {
            "records": [{"Id": "012A", "DeveloperName": "Business"}]
        }
        client, transport = make_async_client(content=render_json_bytes(payload))
        service = AsyncSalesforceRecordTypeLookupService(client)

        rows = await service.list("Account", developer_name="Business")

        soql = transport.send.call_args[0][0].params.get("q", "")
        assert "DeveloperName = 'Business'" in soql
        assert rows == payload["records"]

    async def test_async_record_type_list_returns_empty_on_non_dict_payload(
        self,
    ) -> None:
        client, _ = make_async_client(content=render_json_bytes([1, 2, 3]))
        service = AsyncSalesforceRecordTypeLookupService(client)

        rows = await service.list("Account")

        assert rows == []

    async def test_async_record_type_get_by_developer_name_returns_first_row(
        self,
    ) -> None:
        payload: dict[str, Any] = {"records": [{"Id": "012A"}, {"Id": "012B"}]}
        client, transport = make_async_client(content=render_json_bytes(payload))
        service = AsyncSalesforceRecordTypeLookupService(client)

        row = await service.get_by_developer_name("Account", "Business")

        soql = transport.send.call_args[0][0].params.get("q", "")
        assert "LIMIT 1" in soql
        assert row == payload["records"][0]
