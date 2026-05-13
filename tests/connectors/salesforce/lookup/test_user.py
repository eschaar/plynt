"""Tests for Salesforce User lookup services."""

from __future__ import annotations

from typing import Any

from plynth.connectors.salesforce.lookup import (
    AsyncSalesforceUserLookupService,
    SalesforceUserLookupService,
)
from tests.connectors.salesforce.conftest import render_json_bytes
from tests.connectors.salesforce.lookup.conftest import (
    make_async_client,
    make_sync_client,
)


class TestSalesforceUserLookupService:
    """Test sync User lookup behavior."""

    def test_list_builds_user_query_with_filters(self) -> None:
        payload: dict[str, Any] = {"records": [{"Id": "005A", "Username": "john"}]}
        client, transport = make_sync_client(content=render_json_bytes(payload))
        service = SalesforceUserLookupService(client)

        rows = service.list(
            username="john@example.com",
            email="john@example.com",
            alias="john",
            federation_id="ext-123",
            is_active=True,
        )

        soql = transport.send.call_args[0][0].params.get("q", "")
        assert "FROM User" in soql
        assert "Username = 'john@example.com'" in soql
        assert "Email = 'john@example.com'" in soql
        assert "Alias = 'john'" in soql
        assert "FederationIdentifier = 'ext-123'" in soql
        assert "IsActive = true" in soql
        assert rows == payload["records"]

    def test_get_by_username_returns_none_when_missing(self) -> None:
        client, _ = make_sync_client(content=render_json_bytes({"records": []}))
        service = SalesforceUserLookupService(client)

        row = service.get_by_username("missing@example.com")

        assert row is None


class TestAsyncSalesforceUserLookupService:
    """Test async User lookup behavior."""

    async def test_async_user_get_by_username_returns_row(self) -> None:
        payload: dict[str, Any] = {"records": [{"Id": "005A", "Username": "john"}]}
        client, transport = make_async_client(content=render_json_bytes(payload))
        service = AsyncSalesforceUserLookupService(client)

        row = await service.get_by_username("john@example.com")

        soql = transport.send.call_args[0][0].params.get("q", "")
        assert "Username = 'john@example.com'" in soql
        assert "LIMIT 1" in soql
        assert row == payload["records"][0]

    async def test_async_query_path_uses_explicit_api_version_when_provided(
        self,
    ) -> None:
        payload: dict[str, Any] = {"records": [{"Id": "005A"}]}
        client, transport = make_async_client(content=render_json_bytes(payload))
        service = AsyncSalesforceUserLookupService(client, api_version="61.0")

        await service.list(username="john@example.com")

        sent = transport.send.call_args[0][0]
        assert sent.url.endswith("/services/data/v61.0/query")
