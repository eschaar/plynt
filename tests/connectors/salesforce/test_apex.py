"""Tests for Salesforce Apex REST convenience services."""

from __future__ import annotations

import json
from typing import Any

from plynt.connectors.salesforce.apex import (
    AsyncSalesforceApexRestService,
    SalesforceApexRestService,
)
from plynt.connectors.salesforce.facade import (
    AsyncSalesforceAPIFacade,
    SalesforceAPIFacade,
)
from plynt.http.client import APIClient, AsyncAPIClient
from tests.conftest import MockAsyncTransport, MockSyncTransport
from tests.connectors.salesforce.conftest import DUMMY_INSTANCE_URL, render_json_bytes


def _make_service(
    *,
    base_url: str = DUMMY_INSTANCE_URL,
    status_code: int = 200,
    content: bytes = b"{}",
) -> tuple[SalesforceApexRestService, MockSyncTransport]:
    """Create a sync Apex REST service with mocked transport."""
    transport = MockSyncTransport(status_code=status_code, content=content)
    client = APIClient(base_url=base_url, transport=transport)
    return SalesforceApexRestService(client), transport


def _make_async_service(
    *,
    base_url: str = DUMMY_INSTANCE_URL,
    status_code: int = 200,
    content: bytes = b"{}",
) -> tuple[AsyncSalesforceApexRestService, MockAsyncTransport]:
    """Create an async Apex REST service with mocked transport."""
    transport = MockAsyncTransport(status_code=status_code, content=content)
    client = AsyncAPIClient(base_url=base_url, transport=transport)
    return AsyncSalesforceApexRestService(client), transport


class TestSalesforceApexRestService:
    """Test suite for SalesforceApexRestService."""

    def test_execute_routes_to_apexrest_path(self) -> None:
        """Validate execute() sends requests to /services/apexrest/* paths."""
        payload: dict[str, Any] = {"status": "ok"}
        service, transport = _make_service(content=render_json_bytes(payload))

        result = service.execute("Invoices")

        sent = transport.send.call_args[0][0]
        assert sent.url.endswith("/services/apexrest/Invoices")
        assert result == payload

    def test_execute_passes_method_data_params_and_headers(self) -> None:
        """Validate execute() forwards method, body, params, and headers."""
        service, transport = _make_service(content=render_json_bytes({"ok": True}))

        service.execute(
            "/Invoices/next",
            method="POST",
            data={"amount": 12},
            params={"expand": "true"},
            headers={"X-Trace": "abc"},
        )

        sent = transport.send.call_args[0][0]
        assert sent.method == "POST"
        assert sent.params == {"expand": "true"}
        assert sent.headers.get("X-Trace") == "abc"
        assert sent.content is not None
        assert json.loads(sent.content) == {"amount": 12}

    def test_execute_returns_none_for_empty_body(self) -> None:
        """Validate execute() returns None when response body is empty."""
        service, _ = _make_service(status_code=204, content=b"")

        result = service.execute("Invoices", method="DELETE")

        assert result is None

    def test_facade_apex_rest_returns_service(self) -> None:
        """Validate facade.apex_rest() returns SalesforceApexRestService."""
        transport = MockSyncTransport(status_code=200, content=b"{}")
        client = APIClient(base_url=DUMMY_INSTANCE_URL, transport=transport)
        facade = SalesforceAPIFacade(client)

        service = facade.apex_rest()

        assert isinstance(service, SalesforceApexRestService)


class TestAsyncSalesforceApexRestService:
    """Test suite for AsyncSalesforceApexRestService."""

    async def test_execute_routes_to_apexrest_path(self) -> None:
        """Validate execute() sends requests to /services/apexrest/* paths."""
        payload: dict[str, Any] = {"status": "ok"}
        service, transport = _make_async_service(content=render_json_bytes(payload))

        result = await service.execute("Invoices")

        sent = transport.send.call_args[0][0]
        assert sent.url.endswith("/services/apexrest/Invoices")
        assert result == payload

    async def test_execute_passes_method_data_params_and_headers(self) -> None:
        """Validate execute() forwards method, body, params, and headers."""
        service, transport = _make_async_service(
            content=render_json_bytes({"ok": True})
        )

        await service.execute(
            "/Invoices/next",
            method="PATCH",
            data={"amount": 13},
            params={"expand": "false"},
            headers={"X-Trace": "xyz"},
        )

        sent = transport.send.call_args[0][0]
        assert sent.method == "PATCH"
        assert sent.params == {"expand": "false"}
        assert sent.headers.get("X-Trace") == "xyz"
        assert sent.content is not None
        assert json.loads(sent.content) == {"amount": 13}

    async def test_execute_returns_none_for_empty_body(self) -> None:
        """Validate execute() returns None when response body is empty."""
        service, _ = _make_async_service(status_code=204, content=b"")

        result = await service.execute("Invoices", method="DELETE")

        assert result is None

    def test_facade_apex_rest_returns_service(self) -> None:
        """Validate facade.apex_rest() returns AsyncSalesforceApexRestService."""
        transport = MockAsyncTransport(status_code=200, content=b"{}")
        client = AsyncAPIClient(base_url=DUMMY_INSTANCE_URL, transport=transport)
        facade = AsyncSalesforceAPIFacade(client)

        service = facade.apex_rest()

        assert isinstance(service, AsyncSalesforceApexRestService)
