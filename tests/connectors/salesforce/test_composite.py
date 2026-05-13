# pyright: reportPrivateUsage=false
# pylint: disable=protected-access
"""Tests for Salesforce composite REST services."""

from __future__ import annotations

import json
from typing import Any

from plynth.connectors.salesforce.composite import (
    AsyncSalesforceCompositeService,
    CompositeBatchResponse,
    CompositeBatchSubrequest,
    CompositeResponse,
    CompositeSubrequest,
    CompositeTreeResponse,
    SalesforceCompositeService,
)
from plynth.connectors.salesforce.facade import (
    AsyncSalesforceAPIFacade,
    SalesforceAPIFacade,
)
from plynth.connectors.salesforce.models import SObjectError
from plynth.connectors.salesforce.sobject import DEFAULT_API_VERSION
from plynth.http.client import APIClient, AsyncAPIClient
from tests.conftest import MockAsyncTransport, MockSyncTransport
from tests.connectors.salesforce.conftest import DUMMY_INSTANCE_URL, render_json_bytes


def _make_service(
    *,
    status_code: int = 200,
    content: bytes = b"{}",
) -> tuple[SalesforceCompositeService, MockSyncTransport]:
    """Build a sync composite service backed by a mock transport."""
    transport = MockSyncTransport(status_code=status_code, content=content)
    client = APIClient(base_url=DUMMY_INSTANCE_URL, transport=transport)
    return SalesforceCompositeService(client), transport


def _make_async_service(
    *,
    status_code: int = 200,
    content: bytes = b"{}",
    api_version: str | None = None,
) -> tuple[AsyncSalesforceCompositeService, MockAsyncTransport]:
    """Build an async composite service backed by a mock transport."""
    transport = MockAsyncTransport(status_code=status_code, content=content)
    client = AsyncAPIClient(base_url=DUMMY_INSTANCE_URL, transport=transport)
    return AsyncSalesforceCompositeService(client, api_version=api_version), transport


class TestSalesforceCompositeService:
    """Sync composite service tests."""

    def test_composite_posts_generic_payload(self) -> None:
        """composite() serialises request primitives and returns a typed response."""
        payload: dict[str, Any] = {
            "hasErrors": False,
            "compositeResponse": [
                {
                    "referenceId": "NewAccount",
                    "httpStatusCode": 201,
                    "body": {"id": "001xxx", "success": True},
                }
            ],
        }
        service, transport = _make_service(content=render_json_bytes(payload))

        result = service.composite(
            [
                {
                    "method": "POST",
                    "url": "/services/data/v59.0/sobjects/Account",
                    "referenceId": "NewAccount",
                    "body": {"Name": "Acme"},
                    "httpHeaders": {"Sforce-Auto-Assign": "FALSE"},
                }
            ],
            all_or_none=True,
            collate_subrequests=True,
        )

        sent = transport.send.call_args[0][0]
        assert sent.method == "POST"
        assert sent.url.endswith(f"/services/data/v{DEFAULT_API_VERSION}/composite")
        assert json.loads(sent.content) == {
            "allOrNone": True,
            "collateSubrequests": True,
            "compositeRequest": [
                {
                    "method": "POST",
                    "url": "/services/data/v59.0/sobjects/Account",
                    "referenceId": "NewAccount",
                    "body": {"Name": "Acme"},
                    "httpHeaders": {"Sforce-Auto-Assign": "FALSE"},
                }
            ],
        }
        assert isinstance(result, CompositeResponse)
        assert result.has_errors is False
        assert result.composite_response[0].reference_id == "NewAccount"
        body = result.composite_response[0].body
        assert isinstance(body, dict)
        assert body["id"] == "001xxx"

    def test_composite_accepts_raw_dict_subrequests(self) -> None:
        """Raw dict subrequests are coerced into typed composite request items."""
        payload: dict[str, Any] = {"hasErrors": False, "compositeResponse": []}
        service, transport = _make_service(content=render_json_bytes(payload))

        service.composite(
            [
                {
                    "method": "GET",
                    "url": "/services/data/v59.0/sobjects/Account/001xxx",
                    "referenceId": "AccountLookup",
                }
            ]
        )

        sent = transport.send.call_args[0][0]
        body = json.loads(sent.content)
        assert body["compositeRequest"][0]["referenceId"] == "AccountLookup"

    def test_composite_accepts_model_subrequests(self) -> None:
        """Typed subrequests pass through the coercion helper unchanged."""
        payload: dict[str, Any] = {"hasErrors": False, "compositeResponse": []}
        service, transport = _make_service(content=render_json_bytes(payload))

        request = CompositeSubrequest.model_validate(
            {
                "method": "GET",
                "url": "/services/data/v59.0/sobjects/Account/001xxx",
                "referenceId": "AccountLookup",
            }
        )
        service.composite([request])

        sent = transport.send.call_args[0][0]
        body = json.loads(sent.content)
        assert body["compositeRequest"][0]["referenceId"] == "AccountLookup"

    def test_batch_accepts_model_subrequests(self) -> None:
        """Typed batch subrequests pass through the coercion helper unchanged."""
        payload: dict[str, Any] = {"hasErrors": False, "results": []}
        service, transport = _make_service(content=render_json_bytes(payload))

        request = CompositeBatchSubrequest.model_validate(
            {
                "method": "GET",
                "url": "/services/data/v59.0/sobjects/Account/001xxx",
                "referenceId": "AccountLookup",
                "richInput": {"Name": "Acme"},
                "httpHeaders": {"Sforce-Auto-Assign": "FALSE"},
            }
        )
        service.batch([request])

        sent = transport.send.call_args[0][0]
        body = json.loads(sent.content)
        assert body["batchRequests"][0]["method"] == "GET"

    def test_tree_accepts_raw_dict_records(self) -> None:
        """Raw tree record dicts are copied into the outgoing payload."""
        payload: dict[str, Any] = {"hasErrors": False, "results": []}
        service, transport = _make_service(content=render_json_bytes(payload))

        service.tree("Account", [{"Name": "Acme"}])

        sent = transport.send.call_args[0][0]
        body = json.loads(sent.content)
        assert body["records"][0]["Name"] == "Acme"

    def test_batch_posts_rich_input(self) -> None:
        """batch() serialises the Salesforce richInput shape and parses results."""
        payload: dict[str, Any] = {
            "hasErrors": False,
            "results": [
                {
                    "statusCode": 201,
                    "referenceId": "CreateAccount",
                    "result": {"id": "001xxx"},
                }
            ],
        }
        service, transport = _make_service(content=render_json_bytes(payload))

        result = service.batch(
            [
                {
                    "method": "POST",
                    "url": "/services/data/v59.0/sobjects/Account",
                    "referenceId": "CreateAccount",
                    "richInput": {"Name": "Acme"},
                }
            ],
            halt_on_error=True,
        )

        sent = transport.send.call_args[0][0]
        batch_path = f"/services/data/v{DEFAULT_API_VERSION}/composite/batch"
        assert sent.url.endswith(batch_path)
        assert json.loads(sent.content)["haltOnError"] is True
        assert json.loads(sent.content)["batchRequests"][0]["richInput"] == {
            "Name": "Acme"
        }
        assert isinstance(result, CompositeBatchResponse)
        assert result.results[0].status_code == 201
        assert result.results[0].reference_id == "CreateAccount"

    def test_tree_posts_records_payload(self) -> None:
        """tree() posts hierarchical records and parses tree results."""
        payload: dict[str, Any] = {
            "hasErrors": False,
            "results": [
                {
                    "referenceId": "Account1",
                    "id": "001xxx",
                    "errors": [],
                }
            ],
        }
        service, transport = _make_service(content=render_json_bytes(payload))

        result = service.tree(
            "Account",
            [{"attributes": {"type": "Account", "referenceId": "Account1"}}],
            all_or_none=True,
        )

        sent = transport.send.call_args[0][0]
        assert sent.url.endswith(
            f"/services/data/v{DEFAULT_API_VERSION}/composite/tree/Account"
        )
        assert json.loads(sent.content) == {
            "allOrNone": True,
            "records": [{"attributes": {"type": "Account", "referenceId": "Account1"}}],
        }
        assert isinstance(result, CompositeTreeResponse)
        assert result.results[0].reference_id == "Account1"
        assert result.results[0].errors == []

    def test_facade_composite_returns_service(self) -> None:
        """The sync facade exposes a SalesforceCompositeService."""
        transport = MockSyncTransport(status_code=200, content=b"{}")
        client = APIClient(base_url=DUMMY_INSTANCE_URL, transport=transport)
        facade = SalesforceAPIFacade(client)

        service = facade.composite()

        assert isinstance(service, SalesforceCompositeService)


class TestAsyncSalesforceCompositeService:
    """Async composite service tests."""

    async def test_composite_posts_generic_payload(self) -> None:
        """composite() serialises request primitives and returns a typed response."""
        payload: dict[str, Any] = {
            "hasErrors": False,
            "compositeResponse": [
                {
                    "referenceId": "NewAccount",
                    "httpStatusCode": 201,
                    "body": {"id": "001xxx", "success": True},
                }
            ],
        }
        service, transport = _make_async_service(content=render_json_bytes(payload))

        result = await service.composite(
            [
                {
                    "method": "POST",
                    "url": "/services/data/v59.0/sobjects/Account",
                    "referenceId": "NewAccount",
                    "body": {"Name": "Acme"},
                    "httpHeaders": {"Sforce-Auto-Assign": "FALSE"},
                }
            ],
            all_or_none=True,
            collate_subrequests=True,
        )

        sent = transport.send.call_args[0][0]
        assert sent.method == "POST"
        assert sent.url.endswith(f"/services/data/v{DEFAULT_API_VERSION}/composite")
        assert json.loads(sent.content)["allOrNone"] is True
        assert isinstance(result, CompositeResponse)
        assert result.composite_response[0].reference_id == "NewAccount"

    async def test_composite_resolves_api_version_from_client(self) -> None:
        """The async service resolves its API version via the client fallback."""
        payload: dict[str, Any] = {"hasErrors": False, "compositeResponse": []}
        service, transport = _make_async_service(
            content=render_json_bytes(payload),
            api_version="62.0",
        )

        await service.composite(
            [
                {
                    "method": "GET",
                    "url": "/services/data/v62.0/sobjects/Account/001xxx",
                    "referenceId": "AccountLookup",
                }
            ]
        )

        sent = transport.send.call_args[0][0]
        assert "/v62.0/" in sent.url

    async def test_batch_accepts_model_subrequests(self) -> None:
        """Typed async batch subrequests pass through the coercion helper unchanged."""
        payload: dict[str, Any] = {"hasErrors": False, "results": []}
        service, transport = _make_async_service(content=render_json_bytes(payload))

        request = CompositeBatchSubrequest.model_validate(
            {
                "method": "GET",
                "url": "/services/data/v59.0/sobjects/Account/001xxx",
                "referenceId": "AccountLookup",
                "richInput": {"Name": "Acme"},
                "httpHeaders": {"Sforce-Auto-Assign": "FALSE"},
            }
        )
        await service.batch([request])

        sent = transport.send.call_args[0][0]
        body = json.loads(sent.content)
        assert body["batchRequests"][0]["method"] == "GET"

    async def test_batch_posts_rich_input(self) -> None:
        """batch() serialises the Salesforce richInput shape and parses results."""
        payload: dict[str, Any] = {
            "hasErrors": False,
            "results": [
                {
                    "statusCode": 201,
                    "referenceId": "CreateAccount",
                    "result": {"id": "001xxx"},
                }
            ],
        }
        service, transport = _make_async_service(content=render_json_bytes(payload))

        result = await service.batch(
            [
                {
                    "method": "POST",
                    "url": "/services/data/v59.0/sobjects/Account",
                    "referenceId": "CreateAccount",
                    "richInput": {"Name": "Acme"},
                }
            ],
            halt_on_error=True,
        )

        sent = transport.send.call_args[0][0]
        batch_path = f"/services/data/v{DEFAULT_API_VERSION}/composite/batch"
        assert sent.url.endswith(batch_path)
        assert json.loads(sent.content)["haltOnError"] is True
        assert isinstance(result, CompositeBatchResponse)
        assert result.results[0].status_code == 201

    async def test_tree_posts_records_payload(self) -> None:
        """tree() posts hierarchical records and parses tree results."""
        payload: dict[str, Any] = {
            "hasErrors": False,
            "results": [
                {
                    "referenceId": "Account1",
                    "id": "001xxx",
                    "errors": [],
                }
            ],
        }
        service, transport = _make_async_service(content=render_json_bytes(payload))

        result = await service.tree(
            "Account",
            [{"attributes": {"type": "Account", "referenceId": "Account1"}}],
        )

        sent = transport.send.call_args[0][0]
        assert sent.url.endswith(
            f"/services/data/v{DEFAULT_API_VERSION}/composite/tree/Account"
        )
        assert json.loads(sent.content) == {
            "allOrNone": False,
            "records": [{"attributes": {"type": "Account", "referenceId": "Account1"}}],
        }
        assert isinstance(result, CompositeTreeResponse)
        assert result.results[0].reference_id == "Account1"

    async def test_facade_composite_returns_service(self) -> None:
        """The async facade exposes an AsyncSalesforceCompositeService."""
        transport = MockAsyncTransport(status_code=200, content=b"{}")
        client = AsyncAPIClient(base_url=DUMMY_INSTANCE_URL, transport=transport)
        facade = AsyncSalesforceAPIFacade(client)

        service = facade.composite()

        assert isinstance(service, AsyncSalesforceCompositeService)


class TestCompositeTreeResponseModels:
    """Model validation for tree errors uses Salesforce SObject errors."""

    def test_tree_error_entries_parse_as_sobject_errors(self) -> None:
        """Tree response errors are parsed into typed SObjectError entries."""
        payload = {
            "hasErrors": True,
            "results": [
                {
                    "referenceId": "Account1",
                    "id": "001xxx",
                    "errors": [
                        {
                            "message": "Required fields are missing: [Name]",
                            "errorCode": "REQUIRED_FIELD_MISSING",
                            "fields": ["Name"],
                        }
                    ],
                }
            ],
        }
        result = CompositeTreeResponse.model_validate(payload)

        assert result.has_errors is True
        assert isinstance(result.results[0].errors[0], SObjectError)
        assert result.results[0].errors[0].error_code == "REQUIRED_FIELD_MISSING"
