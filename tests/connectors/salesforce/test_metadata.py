"""Tests for Salesforce Metadata REST deploy services."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from plynt.base.response import Response
from plynt.connectors.salesforce.errors import (
    MetadataDeployTimeoutError,
    SalesforceMetadataDeployError,
)
from plynt.connectors.salesforce.facade import (
    AsyncSalesforceAPIFacade,
    SalesforceAPIFacade,
)
from plynt.connectors.salesforce.metadata import (
    AsyncSalesforceMetadataService,
    SalesforceMetadataDeployResult,
    SalesforceMetadataService,
)
from plynt.http.client import APIClient, AsyncAPIClient
from tests.conftest import MockAsyncTransport, MockSyncTransport
from tests.connectors.salesforce.conftest import DUMMY_INSTANCE_URL, render_json_bytes

_DEPLOY_ID = "0AfA0000000XYZKAA4"


def _deploy_payload(
    *,
    deploy_id: str = _DEPLOY_ID,
    status: str = "Pending",
    done: bool | None = None,
    success: bool | None = None,
    error_message: str | None = None,
) -> bytes:
    payload: dict[str, Any] = {"id": deploy_id, "status": status}
    if done is not None:
        payload["done"] = done
    if success is not None:
        payload["success"] = success
    if error_message is not None:
        payload["errorMessage"] = error_message
    return render_json_bytes(payload)


def _make_service(
    *,
    base_url: str = DUMMY_INSTANCE_URL,
    status_code: int = 200,
    content: bytes = b"{}",
) -> tuple[SalesforceMetadataService, MockSyncTransport]:
    transport = MockSyncTransport(status_code=status_code, content=content)
    client = APIClient(base_url=base_url, transport=transport)
    return SalesforceMetadataService(client), transport


def _make_async_service(
    *,
    base_url: str = DUMMY_INSTANCE_URL,
    status_code: int = 200,
    content: bytes = b"{}",
) -> tuple[AsyncSalesforceMetadataService, MockAsyncTransport]:
    transport = MockAsyncTransport(status_code=status_code, content=content)
    client = AsyncAPIClient(base_url=base_url, transport=transport)
    return AsyncSalesforceMetadataService(client), transport


class TestSalesforceMetadataModels:
    """Metadata deploy model validation tests."""

    def test_deploy_result_parses_alias_fields(self) -> None:
        payload = {
            "id": _DEPLOY_ID,
            "status": "Failed",
            "errorMessage": "Validation failed",
        }

        result = SalesforceMetadataDeployResult.model_validate(payload)

        assert result.id == _DEPLOY_ID
        assert result.status == "Failed"
        assert result.error_message == "Validation failed"


class TestSalesforceMetadataService:
    """Sync metadata service tests."""

    def test_start_deploy_posts_multipart_payload(self) -> None:
        service, transport = _make_service(content=_deploy_payload(status="Pending"))

        result = service.start_deploy(
            b"PK\x03\x04zip-content",
            options={"checkOnly": True},
        )

        sent = transport.send.call_args[0][0]
        assert sent.method == "POST"
        assert sent.url.endswith("/services/data/v59.0/metadata/deployRequest")
        assert sent.headers["Content-Type"].startswith("multipart/form-data")
        assert sent.content is not None
        assert b'name="entity_content"' in sent.content
        assert b'"checkOnly":true' in sent.content
        assert b'name="file"; filename="package.zip"' in sent.content
        assert b"PK\x03\x04zip-content" in sent.content
        assert result.id == _DEPLOY_ID

    def test_start_deploy_rejects_empty_zip(self) -> None:
        service, _ = _make_service(content=_deploy_payload())

        with pytest.raises(ValueError, match="zip_bytes must not be empty"):
            service.start_deploy(b"")

    def test_get_deploy_passes_include_details_query_param(self) -> None:
        service, transport = _make_service(content=_deploy_payload(status="InProgress"))

        service.get_deploy(_DEPLOY_ID, include_details=True)

        sent = transport.send.call_args[0][0]
        assert sent.method == "GET"
        assert sent.params == {"includeDetails": "true"}

    def test_quick_deploy_posts_validated_id_path(self) -> None:
        service, transport = _make_service(content=_deploy_payload(status="Pending"))

        service.quick_deploy(_DEPLOY_ID)

        sent = transport.send.call_args[0][0]
        assert sent.method == "POST"
        assert sent.url.endswith(
            f"/services/data/v59.0/metadata/deployRequest/{_DEPLOY_ID}"
        )

    def test_cancel_deploy_sends_canceling_status_payload(self) -> None:
        service, transport = _make_service(content=_deploy_payload(status="Canceling"))

        service.cancel_deploy(_DEPLOY_ID)

        sent = transport.send.call_args[0][0]
        assert sent.method == "PATCH"
        assert sent.content is not None
        assert json.loads(sent.content) == {"status": "Canceling"}

    def test_wait_for_deploy_returns_on_success_terminal_status(self) -> None:
        transport = MockSyncTransport()
        transport.send.side_effect = [
            Response(status_code=200, content=_deploy_payload(status="InProgress")),
            Response(status_code=200, content=_deploy_payload(status="Succeeded")),
        ]
        client = APIClient(base_url=DUMMY_INSTANCE_URL, transport=transport)
        service = SalesforceMetadataService(client)

        with patch("plynt.connectors.salesforce.metadata.time.sleep"):
            result = service.wait_for_deploy(_DEPLOY_ID, poll_interval=0.0)

        assert result.status == "Succeeded"

    def test_wait_for_deploy_honors_done_flag_when_present(self) -> None:
        transport = MockSyncTransport()
        transport.send.side_effect = [
            Response(
                status_code=200,
                content=_deploy_payload(status="InProgress", done=False),
            ),
            Response(
                status_code=200,
                content=_deploy_payload(status="InProgress", done=True, success=True),
            ),
        ]
        client = APIClient(base_url=DUMMY_INSTANCE_URL, transport=transport)
        service = SalesforceMetadataService(client)

        with patch("plynt.connectors.salesforce.metadata.time.sleep"):
            result = service.wait_for_deploy(_DEPLOY_ID, poll_interval=0.0)

        assert result.done is True

    def test_wait_for_deploy_raises_for_failed_terminal_status(self) -> None:
        service, _ = _make_service(
            content=_deploy_payload(status="Failed", error_message="Deploy error")
        )

        with pytest.raises(SalesforceMetadataDeployError, match="Deploy error"):
            service.wait_for_deploy(_DEPLOY_ID, poll_interval=0.0)

    def test_wait_for_deploy_raises_timeout(self) -> None:
        transport = MockSyncTransport()
        transport.send.return_value = Response(
            status_code=200,
            content=_deploy_payload(status="Pending"),
        )
        client = APIClient(base_url=DUMMY_INSTANCE_URL, transport=transport)
        service = SalesforceMetadataService(client)

        with (
            patch("plynt.connectors.salesforce.metadata.time.sleep"),
            patch(
                "plynt.connectors.salesforce.metadata.time.monotonic",
                side_effect=[0.0, 2.0],
            ),
            pytest.raises(MetadataDeployTimeoutError),
        ):
            service.wait_for_deploy(_DEPLOY_ID, max_wait=1.0, poll_interval=0.0)

    def test_deploy_and_wait_runs_full_happy_path(self) -> None:
        transport = MockSyncTransport()
        transport.send.side_effect = [
            Response(status_code=200, content=_deploy_payload(status="Pending")),
            Response(status_code=200, content=_deploy_payload(status="Succeeded")),
        ]
        client = APIClient(base_url=DUMMY_INSTANCE_URL, transport=transport)
        service = SalesforceMetadataService(client)

        result = service.deploy_and_wait(
            b"PK\x03\x04zip-content",
            options={"rollbackOnError": True},
            poll_interval=0.0,
        )

        assert result.status == "Succeeded"

    def test_facade_metadata_returns_service(self) -> None:
        transport = MockSyncTransport(status_code=200, content=b"{}")
        client = APIClient(base_url=DUMMY_INSTANCE_URL, transport=transport)
        facade = SalesforceAPIFacade(client)

        service = facade.metadata()

        assert isinstance(service, SalesforceMetadataService)


class TestAsyncSalesforceMetadataService:
    """Async metadata service tests."""

    async def test_start_deploy_posts_multipart_payload(self) -> None:
        service, transport = _make_async_service(
            content=_deploy_payload(status="Pending")
        )

        result = await service.start_deploy(
            b"PK\x03\x04zip-content",
            options={"checkOnly": True},
        )

        sent = transport.send.call_args[0][0]
        assert sent.method == "POST"
        assert sent.url.endswith("/services/data/v59.0/metadata/deployRequest")
        assert sent.headers["Content-Type"].startswith("multipart/form-data")
        assert sent.content is not None
        assert b'name="entity_content"' in sent.content
        assert b'"checkOnly":true' in sent.content
        assert result.id == _DEPLOY_ID

    async def test_start_deploy_rejects_empty_zip(self) -> None:
        service, _ = _make_async_service(content=_deploy_payload())

        with pytest.raises(ValueError, match="zip_bytes must not be empty"):
            await service.start_deploy(b"")

    async def test_get_deploy_passes_include_details_query_param(self) -> None:
        service, transport = _make_async_service(
            content=_deploy_payload(status="InProgress")
        )

        await service.get_deploy(_DEPLOY_ID, include_details=True)

        sent = transport.send.call_args[0][0]
        assert sent.method == "GET"
        assert sent.params == {"includeDetails": "true"}

    async def test_quick_deploy_posts_validated_id_path(self) -> None:
        service, transport = _make_async_service(
            content=_deploy_payload(status="Pending")
        )

        await service.quick_deploy(_DEPLOY_ID)

        sent = transport.send.call_args[0][0]
        assert sent.method == "POST"
        assert sent.url.endswith(
            f"/services/data/v59.0/metadata/deployRequest/{_DEPLOY_ID}"
        )

    async def test_cancel_deploy_sends_canceling_status_payload(self) -> None:
        service, transport = _make_async_service(
            content=_deploy_payload(status="Canceling")
        )

        await service.cancel_deploy(_DEPLOY_ID)

        sent = transport.send.call_args[0][0]
        assert sent.method == "PATCH"
        assert sent.content is not None
        assert json.loads(sent.content) == {"status": "Canceling"}

    async def test_wait_for_deploy_returns_on_success_terminal_status(self) -> None:
        transport = MockAsyncTransport()
        transport.send.side_effect = [
            Response(status_code=200, content=_deploy_payload(status="InProgress")),
            Response(status_code=200, content=_deploy_payload(status="Succeeded")),
        ]
        client = AsyncAPIClient(base_url=DUMMY_INSTANCE_URL, transport=transport)
        service = AsyncSalesforceMetadataService(client)

        with patch(
            "plynt.connectors.salesforce.metadata.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            result = await service.wait_for_deploy(_DEPLOY_ID, poll_interval=0.0)

        assert result.status == "Succeeded"

    async def test_wait_for_deploy_raises_for_failed_terminal_status(self) -> None:
        service, _ = _make_async_service(
            content=_deploy_payload(status="Failed", error_message="Deploy error")
        )

        with pytest.raises(SalesforceMetadataDeployError, match="Deploy error"):
            await service.wait_for_deploy(_DEPLOY_ID, poll_interval=0.0)

    async def test_wait_for_deploy_raises_timeout(self) -> None:
        transport = MockAsyncTransport()
        transport.send.return_value = Response(
            status_code=200,
            content=_deploy_payload(status="Pending"),
        )
        client = AsyncAPIClient(base_url=DUMMY_INSTANCE_URL, transport=transport)
        service = AsyncSalesforceMetadataService(client)

        with (
            patch(
                "plynt.connectors.salesforce.metadata.asyncio.sleep",
                new_callable=AsyncMock,
            ),
            patch(
                "plynt.connectors.salesforce.metadata.time.monotonic",
                side_effect=[0.0, 2.0],
            ),
            pytest.raises(MetadataDeployTimeoutError),
        ):
            await service.wait_for_deploy(_DEPLOY_ID, max_wait=1.0, poll_interval=0.0)

    async def test_deploy_and_wait_runs_full_happy_path(self) -> None:
        transport = MockAsyncTransport()
        transport.send.side_effect = [
            Response(status_code=200, content=_deploy_payload(status="Pending")),
            Response(status_code=200, content=_deploy_payload(status="Succeeded")),
        ]
        client = AsyncAPIClient(base_url=DUMMY_INSTANCE_URL, transport=transport)
        service = AsyncSalesforceMetadataService(client)

        result = await service.deploy_and_wait(
            b"PK\x03\x04zip-content",
            options={"rollbackOnError": True},
            poll_interval=0.0,
        )

        assert result.status == "Succeeded"

    def test_facade_metadata_returns_service(self) -> None:
        transport = MockAsyncTransport(status_code=200, content=b"{}")
        client = AsyncAPIClient(base_url=DUMMY_INSTANCE_URL, transport=transport)
        facade = AsyncSalesforceAPIFacade(client)

        service = facade.metadata()

        assert isinstance(service, AsyncSalesforceMetadataService)
