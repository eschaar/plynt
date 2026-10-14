"""Tests for SalesforceObjectService and AsyncSalesforceObjectService.

All HTTP calls are mocked at the transport level — no real network calls.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from plynt.connectors.salesforce.facade import (
    AsyncSalesforceAPIFacade,
    SalesforceAPIFacade,
)
from plynt.connectors.salesforce.models import (
    SObjectCreateResult,
    SObjectPayload,
)
from plynt.connectors.salesforce.renderer import SalesforceRenderer
from plynt.connectors.salesforce.sobject import (
    DEFAULT_API_VERSION,
    AsyncSalesforceObjectService,
    SalesforceObjectService,
)
from plynt.http.client import APIClient, AsyncAPIClient
from plynt.http.renderer import JSONRenderer
from tests.conftest import MockAsyncTransport, MockSyncTransport

BASE_URL = "https://myorg.my.salesforce.com"
OBJECT_NAME = "Account"
RECORD_ID = "001xx000003GYWJAA4"
EXT_FIELD = "My_External_Id__c"
EXT_VALUE = "EXT-001"
_JSON_RENDERER = JSONRenderer()
START_DT = datetime(2026, 1, 1, tzinfo=UTC)
END_DT = datetime(2026, 1, 2, tzinfo=UTC)


def _json_bytes(data: Any) -> bytes:
    """Render test payloads to JSON bytes via the shared renderer layer."""
    return _JSON_RENDERER.render(data)


def _make_service(
    status_code: int = 200,
    content: bytes = b"{}",
    object_name: str = OBJECT_NAME,
    api_version: str = DEFAULT_API_VERSION,
) -> tuple[SalesforceObjectService, MockSyncTransport]:
    """Handle make service."""
    transport = MockSyncTransport(status_code=status_code, content=content)
    client = APIClient(base_url=BASE_URL, transport=transport)
    service = SalesforceObjectService(client, object_name, api_version=api_version)
    return service, transport


class TestSalesforceObjectServicePaths:
    """Verify that the correct URL paths are sent to the transport."""

    def test_get_record_path(self) -> None:
        """Validate get record path."""
        svc, transport = _make_service(content=b'{"Id": "123"}')
        svc.get(RECORD_ID)
        sent = transport.send.call_args[0][0]
        assert sent.url == (
            f"{BASE_URL}/services/data/v{DEFAULT_API_VERSION}"
            f"/sobjects/{OBJECT_NAME}/{RECORD_ID}"
        )

    def test_get_record_with_fields_param(self) -> None:
        """Validate get record with fields param."""
        svc, transport = _make_service(content=b'{"Id": "123", "Name": "X"}')
        svc.get(RECORD_ID, fields=["Id", "Name"])
        sent = transport.send.call_args[0][0]
        assert sent.params == {"fields": "Id,Name"}

    def test_get_by_external_id_path(self) -> None:
        """Validate get by external id path."""
        svc, transport = _make_service(content=b'{"Id": "123"}')
        svc.get_by_external_id(EXT_FIELD, EXT_VALUE)
        sent = transport.send.call_args[0][0]
        assert f"/sobjects/{OBJECT_NAME}/{EXT_FIELD}/{EXT_VALUE}" in sent.url

    def test_create_path_and_method(self) -> None:
        """Validate create path and method."""
        body = _json_bytes({"id": "new123", "success": True, "errors": []})
        svc, transport = _make_service(status_code=201, content=body)
        svc.create({"Name": "ACME Corp"})
        sent = transport.send.call_args[0][0]
        assert sent.method == "POST"
        assert sent.url.endswith(f"/sobjects/{OBJECT_NAME}")

    def test_update_path_and_method(self) -> None:
        """Validate update path and method."""
        svc, transport = _make_service(status_code=204, content=b"")
        svc.update(RECORD_ID, {"Phone": "+31201234567"})
        sent = transport.send.call_args[0][0]
        assert sent.method == "PATCH"
        assert RECORD_ID in sent.url

    def test_upsert_path_and_method(self) -> None:
        """Validate upsert path and method."""
        svc, transport = _make_service(status_code=204, content=b"")
        svc.upsert(EXT_FIELD, EXT_VALUE, {"Name": "ACME"})
        sent = transport.send.call_args[0][0]
        assert sent.method == "PATCH"
        assert f"/{EXT_FIELD}/{EXT_VALUE}" in sent.url

    def test_delete_path_and_method(self) -> None:
        """Validate delete path and method."""
        svc, transport = _make_service(status_code=204, content=b"")
        svc.delete(RECORD_ID)
        sent = transport.send.call_args[0][0]
        assert sent.method == "DELETE"
        assert RECORD_ID in sent.url

    def test_describe_path(self) -> None:
        """Validate describe path."""
        svc, transport = _make_service(content=b'{"name": "Account"}')
        svc.describe()
        sent = transport.send.call_args[0][0]
        assert sent.url.endswith(f"/sobjects/{OBJECT_NAME}/describe")

    def test_metadata_path(self) -> None:
        """Validate metadata path."""
        svc, transport = _make_service(content=b'{"name": "Account"}')
        svc.metadata()
        sent = transport.send.call_args[0][0]
        assert sent.url.endswith(f"/sobjects/{OBJECT_NAME}")

    def test_describe_layout_path(self) -> None:
        """Validate describe layout path."""
        svc, transport = _make_service(content=b'{"layouts": []}')
        svc.describe_layout(RECORD_ID)
        sent = transport.send.call_args[0][0]
        assert sent.url.endswith(
            f"/sobjects/{OBJECT_NAME}/describe/layouts/{RECORD_ID}"
        )

    def test_deleted_path_and_params(self) -> None:
        """Validate deleted path and params."""
        svc, transport = _make_service(content=b'{"deletedRecords": []}')
        svc.deleted(START_DT, END_DT)
        sent = transport.send.call_args[0][0]
        assert sent.url.endswith(f"/sobjects/{OBJECT_NAME}/deleted")
        assert sent.params == {
            "start": START_DT.isoformat(),
            "end": END_DT.isoformat(),
        }

    def test_updated_path_and_params(self) -> None:
        """Validate updated path and params."""
        svc, transport = _make_service(content=b'{"ids": []}')
        svc.updated(START_DT, END_DT)
        sent = transport.send.call_args[0][0]
        assert sent.url.endswith(f"/sobjects/{OBJECT_NAME}/updated")
        assert sent.params == {
            "start": START_DT.isoformat(),
            "end": END_DT.isoformat(),
        }

    def test_custom_api_version_in_path(self) -> None:
        """Validate custom api version in path."""
        svc, transport = _make_service(content=b"{}", api_version="60.0")
        svc.get(RECORD_ID)
        sent = transport.send.call_args[0][0]
        assert "/services/data/v60.0/" in sent.url


class TestSalesforceObjectServiceReturnValues:
    """Verify that return values are parsed and typed correctly."""

    def test_get_returns_dict(self) -> None:
        """Validate get returns dict."""
        payload = {"Id": RECORD_ID, "Name": "ACME Corp"}
        svc, _ = _make_service(content=_json_bytes(payload))
        result = svc.get(RECORD_ID)
        assert result == payload

    def test_get_by_external_id_returns_dict(self) -> None:
        """Validate get by external id returns dict."""
        payload = {"Id": RECORD_ID, "My_External_Id__c": EXT_VALUE}
        svc, _ = _make_service(content=_json_bytes(payload))
        result = svc.get_by_external_id(EXT_FIELD, EXT_VALUE)
        assert result == payload

    def test_create_returns_sobjectcreateresult(self) -> None:
        """Validate create returns sobjectcreateresult."""
        payload = {"id": "abc123", "success": True, "errors": []}
        svc, _ = _make_service(status_code=201, content=_json_bytes(payload))
        result = svc.create({"Name": "ACME"})
        assert isinstance(result, SObjectCreateResult)
        assert result.id == "abc123"
        assert result.success is True

    def test_update_returns_none(self) -> None:
        """Validate update returns none."""
        svc, _ = _make_service(status_code=204, content=b"")
        svc.update(RECORD_ID, {"Name": "Updated"})

    def test_upsert_returns_sobjectcreateresult_on_create(self) -> None:
        """Validate upsert returns sobjectcreateresult on create."""
        payload = {"id": "new123", "success": True, "errors": []}
        svc, _ = _make_service(status_code=201, content=_json_bytes(payload))
        result = svc.upsert(EXT_FIELD, EXT_VALUE, {"Name": "New"})
        assert isinstance(result, SObjectCreateResult)
        assert result.id == "new123"

    def test_upsert_returns_none_on_update(self) -> None:
        """Validate upsert returns none on update."""
        svc, _ = _make_service(status_code=204, content=b"")
        result = svc.upsert(EXT_FIELD, EXT_VALUE, {"Name": "Updated"})
        assert result is None

    def test_delete_returns_none(self) -> None:
        """Validate delete returns none."""
        svc, _ = _make_service(status_code=204, content=b"")
        svc.delete(RECORD_ID)

    def test_describe_returns_dict(self) -> None:
        """Validate describe returns dict."""
        payload = {"name": "Account", "fields": []}
        svc, _ = _make_service(content=_json_bytes(payload))
        result = svc.describe()
        assert result == payload

    def test_metadata_returns_dict(self) -> None:
        """Validate metadata returns dict."""
        payload = {"name": "Account", "label": "Account"}
        svc, _ = _make_service(content=_json_bytes(payload))
        result = svc.metadata()
        assert result == payload

    def test_describe_layout_returns_dict(self) -> None:
        """Validate describe layout returns dict."""
        payload = {"layouts": [{"id": "layout-1"}]}
        svc, _ = _make_service(content=_json_bytes(payload))
        result = svc.describe_layout(RECORD_ID)
        assert result == payload

    def test_deleted_returns_dict(self) -> None:
        """Validate deleted returns dict."""
        payload = {
            "deletedRecords": [],
            "earliestDateAvailable": "2026-01-01T00:00:00+00:00",
        }
        svc, _ = _make_service(content=_json_bytes(payload))
        result = svc.deleted(START_DT, END_DT)
        assert result == payload

    def test_updated_returns_dict(self) -> None:
        """Validate updated returns dict."""
        payload = {"ids": [RECORD_ID], "latestDateCovered": "2026-01-02T00:00:00+00:00"}
        svc, _ = _make_service(content=_json_bytes(payload))
        result = svc.updated(START_DT, END_DT)
        assert result == payload


class TestSalesforceObjectServiceRequestBody:
    """Verify that request bodies are correctly JSON-encoded."""

    def test_create_encodes_body_as_json(self) -> None:
        """Validate create encodes body as json."""
        data = {"Name": "ACME Corp", "Phone": "+31201234567"}
        svc, transport = _make_service(
            status_code=201,
            content=b'{"id": "x", "success": true, "errors": []}',
        )
        svc.create(data)
        sent = transport.send.call_args[0][0]
        assert json.loads(sent.content) == data

    def test_update_encodes_body_as_json(self) -> None:
        """Validate update encodes body as json."""
        data = {"Phone": "+31201234567"}
        svc, transport = _make_service(status_code=204, content=b"")
        svc.update(RECORD_ID, data)
        sent = transport.send.call_args[0][0]
        assert json.loads(sent.content) == data

    def test_upsert_encodes_body_as_json(self) -> None:
        """Validate upsert encodes body as json."""
        data = {"Name": "ACME"}
        svc, transport = _make_service(status_code=204, content=b"")
        svc.upsert(EXT_FIELD, EXT_VALUE, data)
        sent = transport.send.call_args[0][0]
        assert json.loads(sent.content) == data

    def test_create_accepts_sobjectpayload(self) -> None:
        """Validate create accepts sobjectpayload."""
        from pydantic import Field

        class AccountPayload(SObjectPayload):
            """Represent AccountPayload."""

            name: str = Field(serialization_alias="Name")

        payload = AccountPayload(name="ACME Corp")
        svc, transport = _make_service(
            status_code=201,
            content=b'{"id": "x", "success": true, "errors": []}',
        )
        svc.create(payload)
        sent = transport.send.call_args[0][0]
        assert json.loads(sent.content) == {"Name": "ACME Corp"}

    def test_update_accepts_sobjectpayload(self) -> None:
        """Validate update accepts sobjectpayload."""
        from pydantic import Field

        class AccountPayload(SObjectPayload):
            """Represent AccountPayload."""

            phone: str = Field(serialization_alias="Phone")

        payload = AccountPayload(phone="+31201234567")
        svc, transport = _make_service(status_code=204, content=b"")
        svc.update(RECORD_ID, payload)
        sent = transport.send.call_args[0][0]
        assert json.loads(sent.content) == {"Phone": "+31201234567"}

    def test_upsert_accepts_sobjectpayload(self) -> None:
        """Validate upsert accepts sobjectpayload."""
        from pydantic import Field

        class AccountPayload(SObjectPayload):
            """Represent AccountPayload."""

            name: str = Field(serialization_alias="Name")

        payload = AccountPayload(name="Via Payload")
        svc, transport = _make_service(status_code=204, content=b"")
        svc.upsert(EXT_FIELD, EXT_VALUE, payload)
        sent = transport.send.call_args[0][0]
        assert json.loads(sent.content) == {"Name": "Via Payload"}


class TestSalesforceObjectServiceIdValidation:
    """Verify fast-fail behaviour for methods that require a Salesforce record ID."""

    def test_is_salesforce_id_true_for_18_char(self) -> None:
        """Validate is salesforce id true for 18 char."""
        assert SalesforceObjectService._is_salesforce_id(RECORD_ID) is True

    def test_is_salesforce_id_true_for_15_char(self) -> None:
        """Validate is salesforce id true for 15 char."""
        assert SalesforceObjectService._is_salesforce_id("001xx000003GYWJ") is True

    def test_is_salesforce_id_false_for_non_id_string(self) -> None:
        """Validate is salesforce id false for non id string."""
        assert SalesforceObjectService._is_salesforce_id("EXT-001") is False

    def test_is_salesforce_id_false_for_wrong_length(self) -> None:
        """Validate is salesforce id false for wrong length."""
        assert SalesforceObjectService._is_salesforce_id("001xx000003GYW") is False

    def test_is_salesforce_id_false_for_non_alphanumeric(self) -> None:
        """Validate is salesforce id false for non alphanumeric."""
        assert SalesforceObjectService._is_salesforce_id("001xx000003GYW-A") is False

    def test_get_raises_on_invalid_record_id(self) -> None:
        """Validate get raises on invalid record id."""
        import pytest

        svc, _ = _make_service()
        with pytest.raises(ValueError, match="Invalid Salesforce record ID"):
            svc.get("not-an-id")

    def test_update_raises_on_invalid_record_id(self) -> None:
        """Validate update raises on invalid record id."""
        import pytest

        svc, _ = _make_service(status_code=204, content=b"")
        with pytest.raises(ValueError, match="Invalid Salesforce record ID"):
            svc.update("not-an-id", {"Name": "X"})

    def test_delete_raises_on_invalid_record_id(self) -> None:
        """Validate delete raises on invalid record id."""
        import pytest

        svc, _ = _make_service(status_code=204, content=b"")
        with pytest.raises(ValueError, match="Invalid Salesforce record ID"):
            svc.delete("not-an-id")

    def test_describe_layout_raises_on_invalid_record_id(self) -> None:
        """Validate describe layout raises on invalid record id."""
        import pytest

        svc, _ = _make_service()
        with pytest.raises(ValueError, match="Invalid Salesforce record ID"):
            svc.describe_layout("not-an-id")


class TestSalesforceAPIFacade:
    """Verify sync facade delegates to SalesforceObjectService."""

    def test_sobject_returns_bound_service(self) -> None:
        """Validate sobject returns bound service."""
        transport = MockSyncTransport(status_code=200, content=b"{}")
        client = APIClient(base_url=BASE_URL, transport=transport)
        facade = SalesforceAPIFacade(client)
        service = facade.sobject(OBJECT_NAME)
        assert isinstance(service, SalesforceObjectService)
        assert service._object_name == OBJECT_NAME


class TestSalesforceObjectServiceRenderer:
    """Verify renderer injection and default renderer behaviour."""

    def test_default_renderer_is_salesforce_renderer(self) -> None:
        """Validate default renderer is salesforce renderer."""
        transport = MockSyncTransport(status_code=200, content=b"{}")
        client = APIClient(base_url=BASE_URL, transport=transport)
        svc = SalesforceObjectService(client, OBJECT_NAME)
        assert isinstance(svc._renderer, SalesforceRenderer)

    def test_custom_renderer_is_stored(self) -> None:
        """Validate custom renderer is stored."""
        transport = MockSyncTransport(status_code=200, content=b"{}")
        client = APIClient(base_url=BASE_URL, transport=transport)
        custom = SalesforceRenderer()
        svc = SalesforceObjectService(client, OBJECT_NAME, renderer=custom)
        assert svc._renderer is custom

    def test_custom_renderer_is_used_for_create(self) -> None:
        """Injecting a custom renderer causes its render() to be called."""
        from unittest.mock import MagicMock

        mock_renderer = MagicMock()
        mock_renderer.render.return_value = b'{"Name": "Mocked"}'
        transport = MockSyncTransport(
            status_code=201,
            content=b'{"id": "x", "success": true, "errors": []}',
        )
        client = APIClient(base_url=BASE_URL, transport=transport)
        svc = SalesforceObjectService(client, OBJECT_NAME, renderer=mock_renderer)
        svc.create({"Name": "ACME"})
        mock_renderer.render.assert_called_once_with({"Name": "ACME"})


# ===========================================================================
# Async service tests
# ===========================================================================


def _make_async_service(
    status_code: int = 200,
    content: bytes = b"{}",
    object_name: str = OBJECT_NAME,
    api_version: str = DEFAULT_API_VERSION,
) -> tuple[AsyncSalesforceObjectService, MockAsyncTransport]:
    """Handle make async service."""
    transport = MockAsyncTransport(status_code=status_code, content=content)
    client = AsyncAPIClient(base_url=BASE_URL, transport=transport)
    service = AsyncSalesforceObjectService(client, object_name, api_version=api_version)
    return service, transport


class TestAsyncSalesforceObjectServicePaths:
    """Verify that the correct URL paths are sent to the async transport."""

    async def test_get_record_path(self) -> None:
        """Validate get record path."""
        svc, transport = _make_async_service(content=b'{"Id": "123"}')
        await svc.get(RECORD_ID)
        sent = transport.send.call_args[0][0]
        assert sent.url == (
            f"{BASE_URL}/services/data/v{DEFAULT_API_VERSION}"
            f"/sobjects/{OBJECT_NAME}/{RECORD_ID}"
        )

    async def test_get_record_with_fields_param(self) -> None:
        """Validate get record with fields param."""
        svc, transport = _make_async_service(content=b'{"Id": "123", "Name": "X"}')
        await svc.get(RECORD_ID, fields=["Id", "Name"])
        sent = transport.send.call_args[0][0]
        assert sent.params == {"fields": "Id,Name"}

    async def test_get_by_external_id_path(self) -> None:
        """Validate get by external id path."""
        svc, transport = _make_async_service(content=b'{"Id": "123"}')
        await svc.get_by_external_id(EXT_FIELD, EXT_VALUE)
        sent = transport.send.call_args[0][0]
        assert f"/sobjects/{OBJECT_NAME}/{EXT_FIELD}/{EXT_VALUE}" in sent.url

    async def test_create_path_and_method(self) -> None:
        """Validate create path and method."""
        body = _json_bytes({"id": "new123", "success": True, "errors": []})
        svc, transport = _make_async_service(status_code=201, content=body)
        await svc.create({"Name": "ACME Corp"})
        sent = transport.send.call_args[0][0]
        assert sent.method == "POST"
        assert sent.url.endswith(f"/sobjects/{OBJECT_NAME}")

    async def test_update_path_and_method(self) -> None:
        """Validate update path and method."""
        svc, transport = _make_async_service(status_code=204, content=b"")
        await svc.update(RECORD_ID, {"Phone": "+31201234567"})
        sent = transport.send.call_args[0][0]
        assert sent.method == "PATCH"
        assert RECORD_ID in sent.url

    async def test_upsert_path_and_method(self) -> None:
        """Validate upsert path and method."""
        svc, transport = _make_async_service(status_code=204, content=b"")
        await svc.upsert(EXT_FIELD, EXT_VALUE, {"Name": "ACME"})
        sent = transport.send.call_args[0][0]
        assert sent.method == "PATCH"
        assert f"/{EXT_FIELD}/{EXT_VALUE}" in sent.url

    async def test_delete_path_and_method(self) -> None:
        """Validate delete path and method."""
        svc, transport = _make_async_service(status_code=204, content=b"")
        await svc.delete(RECORD_ID)
        sent = transport.send.call_args[0][0]
        assert sent.method == "DELETE"
        assert RECORD_ID in sent.url

    async def test_describe_path(self) -> None:
        """Validate describe path."""
        svc, transport = _make_async_service(content=b'{"name": "Account"}')
        await svc.describe()
        sent = transport.send.call_args[0][0]
        assert sent.url.endswith(f"/sobjects/{OBJECT_NAME}/describe")

    async def test_metadata_path(self) -> None:
        """Validate metadata path."""
        svc, transport = _make_async_service(content=b'{"name": "Account"}')
        await svc.metadata()
        sent = transport.send.call_args[0][0]
        assert sent.url.endswith(f"/sobjects/{OBJECT_NAME}")

    async def test_describe_layout_path(self) -> None:
        """Validate describe layout path."""
        svc, transport = _make_async_service(content=b'{"layouts": []}')
        await svc.describe_layout(RECORD_ID)
        sent = transport.send.call_args[0][0]
        assert sent.url.endswith(
            f"/sobjects/{OBJECT_NAME}/describe/layouts/{RECORD_ID}"
        )

    async def test_deleted_path_and_params(self) -> None:
        """Validate deleted path and params."""
        svc, transport = _make_async_service(content=b'{"deletedRecords": []}')
        await svc.deleted(START_DT, END_DT)
        sent = transport.send.call_args[0][0]
        assert sent.url.endswith(f"/sobjects/{OBJECT_NAME}/deleted")
        assert sent.params == {
            "start": START_DT.isoformat(),
            "end": END_DT.isoformat(),
        }

    async def test_updated_path_and_params(self) -> None:
        """Validate updated path and params."""
        svc, transport = _make_async_service(content=b'{"ids": []}')
        await svc.updated(START_DT, END_DT)
        sent = transport.send.call_args[0][0]
        assert sent.url.endswith(f"/sobjects/{OBJECT_NAME}/updated")
        assert sent.params == {
            "start": START_DT.isoformat(),
            "end": END_DT.isoformat(),
        }

    async def test_custom_api_version_in_path(self) -> None:
        """Validate custom api version in path."""
        svc, transport = _make_async_service(content=b"{}", api_version="60.0")
        await svc.get(RECORD_ID)
        sent = transport.send.call_args[0][0]
        assert "/services/data/v60.0/" in sent.url


class TestAsyncSalesforceObjectServiceReturnValues:
    """Verify that return values are parsed and typed correctly."""

    async def test_get_returns_dict(self) -> None:
        """Validate get returns dict."""
        payload = {"Id": RECORD_ID, "Name": "ACME Corp"}
        svc, _ = _make_async_service(content=_json_bytes(payload))
        result = await svc.get(RECORD_ID)
        assert result == payload

    async def test_get_by_external_id_returns_dict(self) -> None:
        """Validate get by external id returns dict."""
        payload = {"Id": RECORD_ID, "My_External_Id__c": EXT_VALUE}
        svc, _ = _make_async_service(content=_json_bytes(payload))
        result = await svc.get_by_external_id(EXT_FIELD, EXT_VALUE)
        assert result == payload

    async def test_create_returns_sobjectcreateresult(self) -> None:
        """Validate create returns sobjectcreateresult."""
        payload = {"id": "abc123", "success": True, "errors": []}
        svc, _ = _make_async_service(status_code=201, content=_json_bytes(payload))
        result = await svc.create({"Name": "ACME"})
        assert isinstance(result, SObjectCreateResult)
        assert result.id == "abc123"
        assert result.success is True

    async def test_update_returns_none(self) -> None:
        """Validate update returns none."""
        svc, _ = _make_async_service(status_code=204, content=b"")
        await svc.update(RECORD_ID, {"Name": "Updated"})

    async def test_upsert_returns_sobjectcreateresult_on_create(self) -> None:
        """Validate upsert returns sobjectcreateresult on create."""
        payload = {"id": "new123", "success": True, "errors": []}
        svc, _ = _make_async_service(status_code=201, content=_json_bytes(payload))
        result = await svc.upsert(EXT_FIELD, EXT_VALUE, {"Name": "New"})
        assert isinstance(result, SObjectCreateResult)
        assert result.id == "new123"

    async def test_upsert_returns_none_on_update(self) -> None:
        """Validate upsert returns none on update."""
        svc, _ = _make_async_service(status_code=204, content=b"")
        result = await svc.upsert(EXT_FIELD, EXT_VALUE, {"Name": "Updated"})
        assert result is None

    async def test_delete_returns_none(self) -> None:
        """Validate delete returns none."""
        svc, _ = _make_async_service(status_code=204, content=b"")
        await svc.delete(RECORD_ID)

    async def test_describe_returns_dict(self) -> None:
        """Validate describe returns dict."""
        payload = {"name": "Account", "fields": []}
        svc, _ = _make_async_service(content=_json_bytes(payload))
        result = await svc.describe()
        assert result == payload

    async def test_metadata_returns_dict(self) -> None:
        """Validate metadata returns dict."""
        payload = {"name": "Account", "label": "Account"}
        svc, _ = _make_async_service(content=_json_bytes(payload))
        result = await svc.metadata()
        assert result == payload

    async def test_describe_layout_returns_dict(self) -> None:
        """Validate describe layout returns dict."""
        payload = {"layouts": [{"id": "layout-1"}]}
        svc, _ = _make_async_service(content=_json_bytes(payload))
        result = await svc.describe_layout(RECORD_ID)
        assert result == payload

    async def test_deleted_returns_dict(self) -> None:
        """Validate deleted returns dict."""
        payload = {
            "deletedRecords": [],
            "earliestDateAvailable": "2026-01-01T00:00:00+00:00",
        }
        svc, _ = _make_async_service(content=_json_bytes(payload))
        result = await svc.deleted(START_DT, END_DT)
        assert result == payload

    async def test_updated_returns_dict(self) -> None:
        """Validate updated returns dict."""
        payload = {"ids": [RECORD_ID], "latestDateCovered": "2026-01-02T00:00:00+00:00"}
        svc, _ = _make_async_service(content=_json_bytes(payload))
        result = await svc.updated(START_DT, END_DT)
        assert result == payload


class TestAsyncSalesforceObjectServiceRequestBody:
    """Verify that request bodies are correctly JSON-encoded."""

    async def test_create_encodes_body_as_json(self) -> None:
        """Validate create encodes body as json."""
        data = {"Name": "ACME Corp", "Phone": "+31201234567"}
        svc, transport = _make_async_service(
            status_code=201,
            content=b'{"id": "x", "success": true, "errors": []}',
        )
        await svc.create(data)
        sent = transport.send.call_args[0][0]
        assert json.loads(sent.content) == data

    async def test_update_encodes_body_as_json(self) -> None:
        """Validate update encodes body as json."""
        data = {"Phone": "+31201234567"}
        svc, transport = _make_async_service(status_code=204, content=b"")
        await svc.update(RECORD_ID, data)
        sent = transport.send.call_args[0][0]
        assert json.loads(sent.content) == data

    async def test_upsert_encodes_body_as_json(self) -> None:
        """Validate upsert encodes body as json."""
        data = {"Name": "ACME"}
        svc, transport = _make_async_service(status_code=204, content=b"")
        await svc.upsert(EXT_FIELD, EXT_VALUE, data)
        sent = transport.send.call_args[0][0]
        assert json.loads(sent.content) == data

    async def test_create_accepts_sobjectpayload(self) -> None:
        """Validate create accepts sobjectpayload."""
        from pydantic import Field

        class AccountPayload(SObjectPayload):
            """Represent AccountPayload."""

            name: str = Field(serialization_alias="Name")

        payload = AccountPayload(name="ACME Corp")
        svc, transport = _make_async_service(
            status_code=201,
            content=b'{"id": "x", "success": true, "errors": []}',
        )
        await svc.create(payload)
        sent = transport.send.call_args[0][0]
        assert json.loads(sent.content) == {"Name": "ACME Corp"}

    async def test_update_accepts_sobjectpayload(self) -> None:
        """Validate update accepts sobjectpayload."""
        from pydantic import Field

        class AccountPayload(SObjectPayload):
            """Represent AccountPayload."""

            phone: str = Field(serialization_alias="Phone")

        payload = AccountPayload(phone="+31201234567")
        svc, transport = _make_async_service(status_code=204, content=b"")
        await svc.update(RECORD_ID, payload)
        sent = transport.send.call_args[0][0]
        assert json.loads(sent.content) == {"Phone": "+31201234567"}

    async def test_upsert_accepts_sobjectpayload(self) -> None:
        """Validate upsert accepts sobjectpayload."""
        from pydantic import Field

        class AccountPayload(SObjectPayload):
            """Represent AccountPayload."""

            name: str = Field(serialization_alias="Name")

        payload = AccountPayload(name="Via Payload")
        svc, transport = _make_async_service(status_code=204, content=b"")
        await svc.upsert(EXT_FIELD, EXT_VALUE, payload)
        sent = transport.send.call_args[0][0]
        assert json.loads(sent.content) == {"Name": "Via Payload"}


class TestAsyncSalesforceObjectServiceIdValidation:
    """Verify fast-fail behaviour for methods that require a Salesforce record ID."""

    async def test_get_raises_on_invalid_record_id(self) -> None:
        """Validate get raises on invalid record id."""
        import pytest

        svc, _ = _make_async_service()
        with pytest.raises(ValueError, match="Invalid Salesforce record ID"):
            await svc.get("not-an-id")

    async def test_update_raises_on_invalid_record_id(self) -> None:
        """Validate update raises on invalid record id."""
        import pytest

        svc, _ = _make_async_service(status_code=204, content=b"")
        with pytest.raises(ValueError, match="Invalid Salesforce record ID"):
            await svc.update("not-an-id", {"Name": "X"})

    async def test_delete_raises_on_invalid_record_id(self) -> None:
        """Validate delete raises on invalid record id."""
        import pytest

        svc, _ = _make_async_service(status_code=204, content=b"")
        with pytest.raises(ValueError, match="Invalid Salesforce record ID"):
            await svc.delete("not-an-id")

    async def test_describe_layout_raises_on_invalid_record_id(self) -> None:
        """Validate describe layout raises on invalid record id."""
        import pytest

        svc, _ = _make_async_service()
        with pytest.raises(ValueError, match="Invalid Salesforce record ID"):
            await svc.describe_layout("not-an-id")


class TestAsyncSalesforceAPIFacade:
    """Verify async facade delegates to AsyncSalesforceObjectService."""

    def test_sobject_returns_bound_async_service(self) -> None:
        """Validate sobject returns bound async service."""
        transport = MockAsyncTransport(status_code=200, content=b"{}")
        client = AsyncAPIClient(base_url=BASE_URL, transport=transport)
        facade = AsyncSalesforceAPIFacade(client)
        service = facade.sobject(OBJECT_NAME)
        assert isinstance(service, AsyncSalesforceObjectService)
        assert service._object_name == OBJECT_NAME


class TestAsyncSalesforceObjectServiceRenderer:
    """Verify renderer injection and default renderer behaviour."""

    def test_default_renderer_is_salesforce_renderer(self) -> None:
        """Validate default renderer is salesforce renderer."""
        transport = MockAsyncTransport(status_code=200, content=b"{}")
        client = AsyncAPIClient(base_url=BASE_URL, transport=transport)
        svc = AsyncSalesforceObjectService(client, OBJECT_NAME)
        assert isinstance(svc._renderer, SalesforceRenderer)

    def test_custom_renderer_is_stored(self) -> None:
        """Validate custom renderer is stored."""
        transport = MockAsyncTransport(status_code=200, content=b"{}")
        client = AsyncAPIClient(base_url=BASE_URL, transport=transport)
        custom = SalesforceRenderer()
        svc = AsyncSalesforceObjectService(client, OBJECT_NAME, renderer=custom)
        assert svc._renderer is custom

    async def test_custom_renderer_is_used_for_create(self) -> None:
        """Validate custom renderer is used for create."""
        from unittest.mock import MagicMock

        mock_renderer = MagicMock()
        mock_renderer.render.return_value = b'{"Name": "Mocked"}'
        transport = MockAsyncTransport(
            status_code=201,
            content=b'{"id": "x", "success": true, "errors": []}',
        )
        client = AsyncAPIClient(base_url=BASE_URL, transport=transport)
        svc = AsyncSalesforceObjectService(client, OBJECT_NAME, renderer=mock_renderer)
        await svc.create({"Name": "ACME"})
        mock_renderer.render.assert_called_once_with({"Name": "ACME"})
