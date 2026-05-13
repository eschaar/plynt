"""Tests for Salesforce identity access primitives services."""

from __future__ import annotations

import json
from typing import Any

import pytest

from plynth.connectors.salesforce.facade import (
    AsyncSalesforceAPIFacade,
    SalesforceAPIFacade,
)
from plynth.connectors.salesforce.identity import (
    AsyncSalesforceIdentityAccessService,
    SalesforceIdentityAccessService,
)
from plynth.http.client import APIClient, AsyncAPIClient
from plynth.http.renderer import JSONRenderer
from tests.conftest import MockAsyncTransport, MockSyncTransport
from tests.connectors.salesforce.conftest import DUMMY_INSTANCE_URL

_JSON_RENDERER = JSONRenderer()
_USER_ID = "005000000000001AAA"
_PERMISSION_SET_ID = "0PS000000000001AAA"
_PERMISSION_SET_GROUP_ID = "0PG000000000001AAA"
_ASSIGNMENT_ID = "0Pa000000000001AAA"


def _json_bytes(data: Any) -> bytes:
    """Render test payloads to JSON bytes."""
    return _JSON_RENDERER.render(data)


def _make_service(
    *,
    status_code: int = 200,
    content: bytes = b"{}",
) -> tuple[SalesforceIdentityAccessService, MockSyncTransport]:
    """Create a sync identity access service bound to a mocked API client."""
    transport = MockSyncTransport(status_code=status_code, content=content)
    client = APIClient(base_url=DUMMY_INSTANCE_URL, transport=transport)
    return SalesforceIdentityAccessService(client), transport


def _make_async_service(
    *,
    status_code: int = 200,
    content: bytes = b"{}",
) -> tuple[AsyncSalesforceIdentityAccessService, MockAsyncTransport]:
    """Create an async identity access service bound to a mocked API client."""
    transport = MockAsyncTransport(status_code=status_code, content=content)
    client = AsyncAPIClient(base_url=DUMMY_INSTANCE_URL, transport=transport)
    return AsyncSalesforceIdentityAccessService(client), transport


class TestIdentityAccessFacadeWiring:
    """Verify facade wiring for identity access services."""

    def test_sync_facade_identity_access_returns_service(self) -> None:
        """Return sync identity service from facade."""
        client = APIClient(base_url=DUMMY_INSTANCE_URL, transport=MockSyncTransport())
        facade = SalesforceAPIFacade(client)

        assert isinstance(facade.identity_access(), SalesforceIdentityAccessService)

    def test_async_facade_identity_access_returns_service(self) -> None:
        """Return async identity service from facade."""
        client = AsyncAPIClient(
            base_url=DUMMY_INSTANCE_URL,
            transport=MockAsyncTransport(),
        )
        facade = AsyncSalesforceAPIFacade(client)

        assert isinstance(
            facade.identity_access(),
            AsyncSalesforceIdentityAccessService,
        )


class TestSalesforceIdentityAccessService:
    """Test suite for SalesforceIdentityAccessService."""

    def test_list_users_builds_query_with_filters(self) -> None:
        """Send filtered SOQL query to the query endpoint."""
        payload = {"records": [{"Id": _USER_ID, "Username": "alice@example.com"}]}
        service, transport = _make_service(content=_json_bytes(payload))

        result = service.list_users(username="alice@example.com", is_active=True)

        sent = transport.send.call_args[0][0]
        assert sent.url.endswith("/services/data/v59.0/query")
        assert sent.params is not None
        q = sent.params["q"]
        assert "FROM User" in q
        assert "Username = 'alice@example.com'" in q
        assert "IsActive = true" in q
        assert result[0]["Id"] == _USER_ID

    def test_assign_permission_set_posts_assignment_payload(self) -> None:
        """Create permission set assignment through sobject endpoint."""
        payload = {"id": _ASSIGNMENT_ID, "success": True, "errors": []}
        service, transport = _make_service(
            status_code=201, content=_json_bytes(payload)
        )

        result = service.assign_permission_set(_USER_ID, _PERMISSION_SET_ID)

        sent = transport.send.call_args[0][0]
        assert sent.method == "POST"
        assert sent.url.endswith(
            "/services/data/v59.0/sobjects/PermissionSetAssignment"
        )
        assert sent.content is not None
        assert json.loads(sent.content) == {
            "AssigneeId": _USER_ID,
            "PermissionSetId": _PERMISSION_SET_ID,
        }
        assert result.id == _ASSIGNMENT_ID
        assert result.success is True

    def test_set_user_active_patches_user(self) -> None:
        """Patch User IsActive value with generic primitive."""
        service, transport = _make_service(status_code=204, content=b"")

        service.set_user_active(_USER_ID, False)

        sent = transport.send.call_args[0][0]
        assert sent.method == "PATCH"
        assert sent.url.endswith(f"/services/data/v59.0/sobjects/User/{_USER_ID}")
        assert sent.content is not None
        assert json.loads(sent.content) == {"IsActive": False}

    def test_revoke_permission_set_group_deletes_assignment(self) -> None:
        """Delete permission set group assignment by assignment id."""
        service, transport = _make_service(status_code=204, content=b"")

        service.revoke_permission_set_group(_ASSIGNMENT_ID)

        sent = transport.send.call_args[0][0]
        assert sent.method == "DELETE"
        assert sent.url.endswith(
            f"/services/data/v59.0/sobjects/PermissionSetGroupAssignment/{_ASSIGNMENT_ID}"
        )

    def test_list_permission_set_assignments_rejects_invalid_user_id(self) -> None:
        """Raise ValueError for malformed user id."""
        service, _ = _make_service()

        with pytest.raises(ValueError, match="user id"):
            service.list_permission_set_assignments("not-a-salesforce-id")


class TestAsyncSalesforceIdentityAccessService:
    """Test suite for AsyncSalesforceIdentityAccessService."""

    @pytest.mark.asyncio
    async def test_list_permission_set_group_assignments_queries_records(self) -> None:
        """Send SOQL for group assignments on async service."""
        payload = {
            "records": [
                {
                    "Id": _ASSIGNMENT_ID,
                    "AssigneeId": _USER_ID,
                    "PermissionSetGroupId": _PERMISSION_SET_GROUP_ID,
                }
            ]
        }
        service, transport = _make_async_service(content=_json_bytes(payload))

        result = await service.list_permission_set_group_assignments(
            _USER_ID,
            permission_set_group_id=_PERMISSION_SET_GROUP_ID,
        )

        sent = transport.send.call_args[0][0]
        assert sent.url.endswith("/services/data/v59.0/query")
        assert sent.params is not None
        q = sent.params["q"]
        assert "FROM PermissionSetGroupAssignment" in q
        assert f"PermissionSetGroupId = '{_PERMISSION_SET_GROUP_ID}'" in q
        assert result[0]["Id"] == _ASSIGNMENT_ID

    @pytest.mark.asyncio
    async def test_assign_permission_set_group_posts_payload(self) -> None:
        """Create group assignment through async sobject endpoint."""
        payload = {"id": _ASSIGNMENT_ID, "success": True, "errors": []}
        service, transport = _make_async_service(
            status_code=201,
            content=_json_bytes(payload),
        )

        result = await service.assign_permission_set_group(
            _USER_ID,
            _PERMISSION_SET_GROUP_ID,
        )

        sent = transport.send.call_args[0][0]
        assert sent.method == "POST"
        assert sent.url.endswith(
            "/services/data/v59.0/sobjects/PermissionSetGroupAssignment"
        )
        assert sent.content is not None
        assert json.loads(sent.content) == {
            "AssigneeId": _USER_ID,
            "PermissionSetGroupId": _PERMISSION_SET_GROUP_ID,
        }
        assert result.id == _ASSIGNMENT_ID
