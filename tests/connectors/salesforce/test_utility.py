"""Tests for Salesforce utility REST service wrappers."""

from __future__ import annotations

import json
from typing import Any

import pytest

from plynt.base.response import Response
from plynt.connectors.salesforce.errors import SalesforceQueryResponseError
from plynt.connectors.salesforce.facade import (
    AsyncSalesforceAPIFacade,
    SalesforceAPIFacade,
)
from plynt.connectors.salesforce.models import (
    SalesforceApiUsage,
    SalesforceApiVersion,
    SalesforceGlobalDescribeResponse,
    SalesforceLimitsResponse,
)
from plynt.connectors.salesforce.sobject import DEFAULT_API_VERSION
from plynt.connectors.salesforce.utility import (
    AsyncSalesforceUtilityService,
    SalesforceUtilityService,
)
from plynt.http.client import APIClient, AsyncAPIClient
from plynt.http.renderer import JSONRenderer
from tests.conftest import MockAsyncTransport, MockSyncTransport
from tests.connectors.salesforce.conftest import DUMMY_INSTANCE_URL

_JSON_RENDERER = JSONRenderer()


def _json_bytes(data: Any) -> bytes:
    """Render test payloads to JSON bytes via the shared renderer layer."""
    return _JSON_RENDERER.render(data)


def _make_service(
    *,
    base_url: str = DUMMY_INSTANCE_URL,
    status_code: int = 200,
    content: bytes = b"{}",
) -> tuple[SalesforceUtilityService, MockSyncTransport]:
    """Create a sync utility service bound to a mocked API client."""
    transport = MockSyncTransport(status_code=status_code, content=content)
    client = APIClient(base_url=base_url, transport=transport)
    return SalesforceUtilityService(client), transport


def _make_async_service(
    *,
    base_url: str = DUMMY_INSTANCE_URL,
    status_code: int = 200,
    content: bytes = b"{}",
) -> tuple[AsyncSalesforceUtilityService, MockAsyncTransport]:
    """Create an async utility service bound to a mocked API client."""
    transport = MockAsyncTransport(status_code=status_code, content=content)
    client = AsyncAPIClient(base_url=base_url, transport=transport)
    return AsyncSalesforceUtilityService(client), transport


class TestSalesforceUtilityService:
    """Test suite for SalesforceUtilityService."""

    def test_versions_path_and_model(self) -> None:
        """Validate versions path and model."""
        payload: list[dict[str, str]] = [
            {"label": "Winter '25", "url": "/services/data/v62.0", "version": "62.0"},
            {"label": "Spring '25", "url": "/services/data/v63.0", "version": "63.0"},
        ]
        svc, transport = _make_service(content=_json_bytes(payload))
        result = svc.versions()
        sent = transport.send.call_args[0][0]
        assert sent.url.endswith("/services/data/")
        assert len(result) == 2
        assert all(isinstance(v, SalesforceApiVersion) for v in result)
        assert result[-1].version == "63.0"
        assert result[-1].label == "Spring '25"
        assert result[-1].url == "/services/data/v63.0"

    def test_limits_path(self) -> None:
        """Validate limits path."""
        payload: dict[str, dict[str, int]] = {
            "DailyApiRequests": {"Max": 15000, "Remaining": 14999}
        }
        svc, transport = _make_service(content=_json_bytes(payload))
        result = svc.limits()
        sent = transport.send.call_args[0][0]
        assert sent.url.endswith(f"/services/data/v{DEFAULT_API_VERSION}/limits")
        assert isinstance(result, SalesforceLimitsResponse)
        assert result.model_dump(by_alias=True) == payload

    def test_limits_parses_api_usage_header(self) -> None:
        """Validate limits() attaches parsed api-usage header metadata."""
        payload: dict[str, dict[str, int]] = {
            "DailyApiRequests": {"Max": 15000, "Remaining": 14999}
        }
        svc, transport = _make_service(content=_json_bytes(payload))
        transport.send.return_value = Response(
            status_code=200,
            headers={"Sforce-Limit-Info": "api-usage=18/5000"},
            content=_json_bytes(payload),
        )

        result = svc.limits()
        assert isinstance(result.api_usage, SalesforceApiUsage)
        assert result.api_usage is not None
        assert result.api_usage.used == 18
        assert result.api_usage.limit == 5000

    def test_limits_ignores_unparseable_limit_info_header(self) -> None:
        """Validate limits() returns without api_usage for unparseable header values."""
        payload: dict[str, dict[str, int]] = {
            "DailyApiRequests": {"Max": 15000, "Remaining": 14999}
        }
        svc, transport = _make_service(content=_json_bytes(payload))
        transport.send.return_value = Response(
            status_code=200,
            headers={"Sforce-Limit-Info": "api-usage=not-a-fraction"},
            content=_json_bytes(payload),
        )

        result = svc.limits()
        assert result.api_usage is None

    def test_objects_path_and_model(self) -> None:
        """Validate objects() path and returned model type."""
        payload: dict[str, Any] = {
            "encoding": "UTF-8",
            "maxBatchSize": 200,
            "sobjects": [
                {
                    "name": "Account",
                    "label": "Account",
                    "labelPlural": "Accounts",
                    "keyPrefix": "001",
                    "queryable": True,
                    "createable": True,
                    "updateable": True,
                    "deletable": True,
                    "searchable": True,
                    "custom": False,
                    "urls": {"sobject": "/services/data/v59.0/sobjects/Account"},
                }
            ],
        }
        svc, transport = _make_service(content=_json_bytes(payload))
        result = svc.objects()
        sent = transport.send.call_args[0][0]
        assert sent.url.endswith(f"/services/data/v{DEFAULT_API_VERSION}/sobjects/")
        assert isinstance(result, SalesforceGlobalDescribeResponse)
        assert result.encoding == "UTF-8"
        assert result.max_batch_size == 200
        assert len(result.sobjects) == 1
        obj = result.sobjects[0]
        assert obj.name == "Account"
        assert obj.queryable is True
        assert obj.key_prefix == "001"

    def test_search_raises_not_implemented_error(self) -> None:
        """search() on utility raises NotImplementedError directing to SearchService."""
        svc, _ = _make_service()
        try:
            svc.search("FIND {x}")
        except NotImplementedError as exc:
            assert "SalesforceSearchService" in str(exc)
        else:
            raise AssertionError("Expected NotImplementedError")

    def test_quick_search_raises_not_implemented_error(self) -> None:
        """quick_search() on utility raises NotImplementedError."""
        svc, _ = _make_service()
        try:
            svc.quick_search("x")
        except NotImplementedError as exc:
            assert "SalesforceSearchService" in str(exc)
        else:
            raise AssertionError("Expected NotImplementedError")

    def test_tooling_execute_get(self) -> None:
        """Validate tooling execute get."""
        payload: dict[str, list[Any]] = {"records": []}
        svc, transport = _make_service(content=_json_bytes(payload))
        result = svc.tooling_execute("query", params={"q": "SELECT Id FROM ApexClass"})
        sent = transport.send.call_args[0][0]
        assert sent.method == "GET"
        assert sent.url.endswith(f"/services/data/v{DEFAULT_API_VERSION}/tooling/query")
        assert sent.params == {"q": "SELECT Id FROM ApexClass"}
        assert result == payload

    def test_tooling_execute_post_encodes_body(self) -> None:
        """Validate tooling execute post encodes body."""
        payload: dict[str, Any] = {"id": "01p...", "success": True}
        svc, transport = _make_service(content=_json_bytes(payload))
        result = svc.tooling_execute(
            "sobjects/TraceFlag",
            method="POST",
            data={"TracedEntityId": "005..."},
        )
        sent = transport.send.call_args[0][0]
        assert sent.method == "POST"
        assert sent.content is not None
        assert json.loads(sent.content) == {"TracedEntityId": "005..."}
        assert result == payload

    def test_tooling_execute_empty_body_returns_none(self) -> None:
        """Validate tooling execute empty body returns none."""
        svc, _ = _make_service(status_code=204, content=b"")
        result = svc.tooling_execute("sobjects/TraceFlag/01p...", method="DELETE")
        assert result is None

    def test_restful_versioned_default_path_and_json_response(self) -> None:
        """Validate restful() uses versioned base path and parses JSON body."""
        payload: dict[str, Any] = {"ok": True}
        svc, transport = _make_service(content=_json_bytes(payload))

        result = svc.restful("custom/path")

        sent = transport.send.call_args[0][0]
        assert sent.url.endswith(f"/services/data/v{DEFAULT_API_VERSION}/custom/path")
        assert result == payload

    def test_restful_unversioned_routes_without_api_prefix(self) -> None:
        """Validate restful_unversioned() routes without versioned API prefix."""
        payload: dict[str, Any] = {"ok": True}
        svc, transport = _make_service(content=_json_bytes(payload))

        result = svc.restful_unversioned("services/apexrest/MyClass")

        sent = transport.send.call_args[0][0]
        assert sent.url.endswith("/services/apexrest/MyClass")
        assert result == payload

    def test_restful_passes_method_data_params_and_headers(self) -> None:
        """Validate restful() forwards method, data, params and headers."""
        payload: dict[str, Any] = {"ok": True}
        svc, transport = _make_service(content=_json_bytes(payload))

        result = svc.restful(
            "custom/path",
            method="POST",
            data={"name": "Acme"},
            params={"expand": "all"},
            headers={"X-Trace": "abc"},
        )

        sent = transport.send.call_args[0][0]
        assert sent.method == "POST"
        assert sent.params == {"expand": "all"}
        assert sent.headers.get("X-Trace") == "abc"
        assert sent.content is not None
        assert json.loads(sent.content) == {"name": "Acme"}
        assert result == payload

    def test_restful_returns_none_for_empty_body(self) -> None:
        """Validate restful() returns None for empty response bodies."""
        svc, _ = _make_service(status_code=204, content=b"")

        result = svc.restful("custom/path", method="DELETE")

        assert result is None

    def test_facade_utility_returns_service(self, salesforce_base_url: str) -> None:
        """Validate facade utility returns service."""
        transport = MockSyncTransport(status_code=200, content=b"{}")
        client = APIClient(base_url=salesforce_base_url, transport=transport)
        facade = SalesforceAPIFacade(client)
        util = facade.utility()
        assert isinstance(util, SalesforceUtilityService)

    def test_is_sandbox_returns_true_for_sandbox_org(self) -> None:
        """Validate is_sandbox() returns True when org is a sandbox."""
        payload = {"totalSize": 1, "done": True, "records": [{"IsSandbox": True}]}
        svc, transport = _make_service(content=_json_bytes(payload))

        result = svc.is_sandbox()

        sent = transport.send.call_args[0][0]
        assert "/query" in sent.url
        assert sent.params.get("q") == "SELECT IsSandbox FROM Organization LIMIT 1"
        assert result is True

    def test_is_sandbox_returns_false_for_production_org(self) -> None:
        """Validate is_sandbox() returns False when org is a production org."""
        payload = {"totalSize": 1, "done": True, "records": [{"IsSandbox": False}]}
        svc, _ = _make_service(content=_json_bytes(payload))

        result = svc.is_sandbox()

        assert result is False

    def test_is_sandbox_raises_typed_error_for_empty_records(self) -> None:
        """Validate is_sandbox() raises a typed error for empty records."""
        payload = {"totalSize": 0, "done": True, "records": []}
        svc, _ = _make_service(content=_json_bytes(payload))

        with pytest.raises(SalesforceQueryResponseError, match="no records"):
            svc.is_sandbox()

    def test_is_sandbox_raises_typed_error_for_missing_field(self) -> None:
        """Validate is_sandbox() raises a typed error for missing field."""
        payload = {"totalSize": 1, "done": True, "records": [{}]}
        svc, _ = _make_service(content=_json_bytes(payload))

        with pytest.raises(SalesforceQueryResponseError, match="missing IsSandbox"):
            svc.is_sandbox()

    def test_is_sandbox_raises_typed_error_for_invalid_payload_shape(self) -> None:
        """Validate is_sandbox() raises typed error for malformed query payload."""
        svc, _ = _make_service(content=_json_bytes({"records": "invalid"}))

        with pytest.raises(SalesforceQueryResponseError, match="invalid shape"):
            svc.is_sandbox()


class TestAsyncSalesforceUtilityService:
    """Test suite for AsyncSalesforceUtilityService."""

    async def test_versions_path_and_model(self) -> None:
        """Validate versions path and model."""
        payload: list[dict[str, str]] = [
            {"label": "Winter '25", "url": "/services/data/v62.0", "version": "62.0"},
            {"label": "Spring '25", "url": "/services/data/v63.0", "version": "63.0"},
        ]
        svc, transport = _make_async_service(content=_json_bytes(payload))
        result = await svc.versions()
        sent = transport.send.call_args[0][0]
        assert sent.url.endswith("/services/data/")
        assert len(result) == 2
        assert all(isinstance(v, SalesforceApiVersion) for v in result)
        assert result[-1].version == "63.0"
        assert result[-1].label == "Spring '25"

    async def test_limits_path(self) -> None:
        """Validate limits path."""
        payload: dict[str, dict[str, int]] = {
            "DailyApiRequests": {"Max": 15000, "Remaining": 14999}
        }
        svc, transport = _make_async_service(content=_json_bytes(payload))
        result = await svc.limits()
        sent = transport.send.call_args[0][0]
        assert sent.url.endswith(f"/services/data/v{DEFAULT_API_VERSION}/limits")
        assert isinstance(result, SalesforceLimitsResponse)
        assert result.model_dump(by_alias=True) == payload

    async def test_limits_parses_api_usage_header(self) -> None:
        """Validate async limits() attaches parsed api-usage header metadata."""
        payload: dict[str, dict[str, int]] = {
            "DailyApiRequests": {"Max": 15000, "Remaining": 14999}
        }
        svc, transport = _make_async_service(content=_json_bytes(payload))
        transport.send.return_value = Response(
            status_code=200,
            headers={"Sforce-Limit-Info": "api-usage=19/5000"},
            content=_json_bytes(payload),
        )

        result = await svc.limits()
        assert isinstance(result.api_usage, SalesforceApiUsage)
        assert result.api_usage is not None
        assert result.api_usage.used == 19
        assert result.api_usage.limit == 5000

    async def test_objects_path_and_model(self) -> None:
        """Validate objects() path and returned model type."""
        payload: dict[str, Any] = {
            "encoding": "UTF-8",
            "maxBatchSize": 200,
            "sobjects": [
                {
                    "name": "Contact",
                    "label": "Contact",
                    "labelPlural": "Contacts",
                    "keyPrefix": "003",
                    "queryable": True,
                    "createable": True,
                    "updateable": True,
                    "deletable": True,
                    "searchable": True,
                    "custom": False,
                    "urls": {"sobject": "/services/data/v59.0/sobjects/Contact"},
                }
            ],
        }
        svc, transport = _make_async_service(content=_json_bytes(payload))
        result = await svc.objects()
        sent = transport.send.call_args[0][0]
        assert sent.url.endswith(f"/services/data/v{DEFAULT_API_VERSION}/sobjects/")
        assert isinstance(result, SalesforceGlobalDescribeResponse)
        assert result.encoding == "UTF-8"
        assert len(result.sobjects) == 1
        assert result.sobjects[0].name == "Contact"

    async def test_search_raises_not_implemented_error(self) -> None:
        """search() on utility raises NotImplementedError directing to SearchService."""
        svc, _ = _make_async_service()
        try:
            await svc.search("FIND {x}")
        except NotImplementedError as exc:
            assert "SalesforceSearchService" in str(exc)
        else:
            raise AssertionError("Expected NotImplementedError")

    async def test_quick_search_raises_not_implemented_error(self) -> None:
        """quick_search() on utility raises NotImplementedError."""
        svc, _ = _make_async_service()
        try:
            await svc.quick_search("x")
        except NotImplementedError as exc:
            assert "SalesforceSearchService" in str(exc)
        else:
            raise AssertionError("Expected NotImplementedError")

    async def test_tooling_execute_get(self) -> None:
        """Validate tooling execute get."""
        payload: dict[str, list[Any]] = {"records": []}
        svc, transport = _make_async_service(content=_json_bytes(payload))
        result = await svc.tooling_execute(
            "query",
            params={"q": "SELECT Id FROM ApexClass"},
        )
        sent = transport.send.call_args[0][0]
        assert sent.method == "GET"
        assert sent.url.endswith(f"/services/data/v{DEFAULT_API_VERSION}/tooling/query")
        assert sent.params == {"q": "SELECT Id FROM ApexClass"}
        assert result == payload

    async def test_tooling_execute_post_encodes_body(self) -> None:
        """Validate tooling execute post encodes body."""
        payload: dict[str, Any] = {"id": "01p...", "success": True}
        svc, transport = _make_async_service(content=_json_bytes(payload))
        result = await svc.tooling_execute(
            "sobjects/TraceFlag",
            method="POST",
            data={"TracedEntityId": "005..."},
        )
        sent = transport.send.call_args[0][0]
        assert sent.method == "POST"
        assert sent.content is not None
        assert json.loads(sent.content) == {"TracedEntityId": "005..."}
        assert result == payload

    async def test_restful_versioned_default_path_and_json_response(self) -> None:
        """Validate async restful() uses versioned base path and parses JSON."""
        payload: dict[str, Any] = {"ok": True}
        svc, transport = _make_async_service(content=_json_bytes(payload))

        result = await svc.restful("custom/path")

        sent = transport.send.call_args[0][0]
        assert sent.url.endswith(f"/services/data/v{DEFAULT_API_VERSION}/custom/path")
        assert result == payload

    async def test_restful_unversioned_routes_without_api_prefix(self) -> None:
        """Validate async restful_unversioned() routes without versioned prefix."""
        payload: dict[str, Any] = {"ok": True}
        svc, transport = _make_async_service(content=_json_bytes(payload))

        result = await svc.restful_unversioned("services/apexrest/MyClass")

        sent = transport.send.call_args[0][0]
        assert sent.url.endswith("/services/apexrest/MyClass")
        assert result == payload

    async def test_restful_passes_method_data_params_and_headers(self) -> None:
        """Validate async restful() forwards method, data, params and headers."""
        payload: dict[str, Any] = {"ok": True}
        svc, transport = _make_async_service(content=_json_bytes(payload))

        result = await svc.restful(
            "custom/path",
            method="PATCH",
            data={"name": "Acme"},
            params={"expand": "all"},
            headers={"X-Trace": "abc"},
        )

        sent = transport.send.call_args[0][0]
        assert sent.method == "PATCH"
        assert sent.params == {"expand": "all"}
        assert sent.headers.get("X-Trace") == "abc"
        assert sent.content is not None
        assert json.loads(sent.content) == {"name": "Acme"}
        assert result == payload

    async def test_restful_returns_none_for_empty_body(self) -> None:
        """Validate async restful() returns None for empty response bodies."""
        svc, _ = _make_async_service(status_code=204, content=b"")

        result = await svc.restful("custom/path", method="DELETE")

        assert result is None

    async def test_tooling_execute_empty_body_returns_none(self) -> None:
        """Validate tooling execute empty body returns none."""
        svc, _ = _make_async_service(status_code=204, content=b"")
        result = await svc.tooling_execute(
            "sobjects/TraceFlag/01p...",
            method="DELETE",
        )
        assert result is None

    async def test_is_sandbox_returns_true_for_sandbox_org(self) -> None:
        """Validate async is_sandbox() returns True when org is a sandbox."""
        payload = {"totalSize": 1, "done": True, "records": [{"IsSandbox": True}]}
        svc, transport = _make_async_service(content=_json_bytes(payload))

        result = await svc.is_sandbox()

        sent = transport.send.call_args[0][0]
        assert "/query" in sent.url
        assert sent.params.get("q") == "SELECT IsSandbox FROM Organization LIMIT 1"
        assert result is True

    async def test_is_sandbox_returns_false_for_production_org(self) -> None:
        """Validate async is_sandbox() returns False when org is a production org."""
        payload = {"totalSize": 1, "done": True, "records": [{"IsSandbox": False}]}
        svc, _ = _make_async_service(content=_json_bytes(payload))

        result = await svc.is_sandbox()

        assert result is False

    async def test_is_sandbox_raises_typed_error_for_empty_records(self) -> None:
        """Validate async is_sandbox() raises a typed error for empty records."""
        payload = {"totalSize": 0, "done": True, "records": []}
        svc, _ = _make_async_service(content=_json_bytes(payload))

        with pytest.raises(SalesforceQueryResponseError, match="no records"):
            await svc.is_sandbox()

    async def test_is_sandbox_raises_typed_error_for_missing_field(self) -> None:
        """Validate async is_sandbox() raises a typed error for missing field."""
        payload = {"totalSize": 1, "done": True, "records": [{}]}
        svc, _ = _make_async_service(content=_json_bytes(payload))

        with pytest.raises(SalesforceQueryResponseError, match="missing IsSandbox"):
            await svc.is_sandbox()

    async def test_is_sandbox_raises_typed_error_for_invalid_payload_shape(
        self,
    ) -> None:
        """Validate async is_sandbox() raises typed error for malformed payload."""
        svc, _ = _make_async_service(content=_json_bytes({"records": "invalid"}))

        with pytest.raises(SalesforceQueryResponseError, match="invalid shape"):
            await svc.is_sandbox()

    def test_facade_utility_returns_service(self, salesforce_base_url: str) -> None:
        """Validate facade utility returns service."""
        transport = MockAsyncTransport(status_code=200, content=b"{}")
        client = AsyncAPIClient(base_url=salesforce_base_url, transport=transport)
        facade = AsyncSalesforceAPIFacade(client)
        util = facade.utility()
        assert isinstance(util, AsyncSalesforceUtilityService)
