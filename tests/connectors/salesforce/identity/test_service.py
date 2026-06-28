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
    return bytes(_JSON_RENDERER.render(data))


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

    # ------------------------------------------------------------------
    # _query_records edge cases
    # ------------------------------------------------------------------

    def test_query_records_returns_empty_for_non_dict_payload(self) -> None:
        """Return empty list when the response body is not a JSON object."""
        service, _ = _make_service(content=b"[]")

        result = service._query_records("SELECT Id FROM User")

        assert result == []

    def test_query_records_returns_empty_when_records_key_absent(self) -> None:
        """Return empty list when the JSON object has no 'records' key."""
        payload = {"totalSize": 0, "done": True}
        service, _ = _make_service(content=_json_bytes(payload))

        result = service._query_records("SELECT Id FROM User")

        assert result == []

    def test_query_records_returns_empty_when_records_is_not_a_list(self) -> None:
        """Return empty list when 'records' is present but not a list."""
        payload = {"records": "unexpected-string"}
        service, _ = _make_service(content=_json_bytes(payload))

        result = service._query_records("SELECT Id FROM User")

        assert result == []

    # ------------------------------------------------------------------
    # get_user
    # ------------------------------------------------------------------

    def test_get_user_returns_user_dict(self) -> None:
        """Return user record dict from SObject endpoint."""
        user_payload = {
            "Id": _USER_ID,
            "Username": "alice@example.com",
            "IsActive": True,
        }
        service, transport = _make_service(content=_json_bytes(user_payload))

        result = service.get_user(_USER_ID)

        sent = transport.send.call_args[0][0]
        assert sent.method == "GET"
        assert sent.url.endswith(f"/services/data/v59.0/sobjects/User/{_USER_ID}")
        assert result["Id"] == _USER_ID

    def test_get_user_with_custom_fields_sends_fields_param(self) -> None:
        """Include custom field list as 'fields' query parameter."""
        service, transport = _make_service(content=_json_bytes({"Id": _USER_ID}))

        service.get_user(_USER_ID, fields=["Id", "Email"])

        sent = transport.send.call_args[0][0]
        assert sent.params is not None
        assert sent.params["fields"] == "Id,Email"

    def test_get_user_returns_empty_dict_for_non_dict_response(self) -> None:
        """Return empty dict when response body is not a JSON object."""
        service, _ = _make_service(content=b"null")

        result = service.get_user(_USER_ID)

        assert result == {}

    def test_get_user_raises_for_invalid_id(self) -> None:
        """Raise ValueError for a malformed user id."""
        service, _ = _make_service()

        with pytest.raises(ValueError, match="user id"):
            service.get_user("bad-id!")

    # ------------------------------------------------------------------
    # list_users
    # ------------------------------------------------------------------

    def test_list_users_returns_empty_list_for_no_results(self) -> None:
        """Return empty list when SOQL query yields no records."""
        payload = {"totalSize": 0, "done": True, "records": []}
        service, _ = _make_service(content=_json_bytes(payload))

        result = service.list_users()

        assert result == []

    def test_list_users_with_all_filters_builds_compound_where(self) -> None:
        """Build SOQL query with all optional filter conditions active."""
        payload: dict[str, list[object]] = {"records": []}
        service, transport = _make_service(content=_json_bytes(payload))

        service.list_users(
            username="alice@example.com",
            email="alice@example.com",
            is_active=True,
            profile_id=_PERMISSION_SET_ID,
        )

        sent = transport.send.call_args[0][0]
        q = sent.params["q"]
        assert "Username = 'alice@example.com'" in q
        assert "Email = 'alice@example.com'" in q
        assert "IsActive = true" in q
        assert f"ProfileId = '{_PERMISSION_SET_ID}'" in q

    def test_list_users_raises_for_invalid_profile_id(self) -> None:
        """Raise ValueError when profile_id is not a valid Salesforce ID."""
        service, _ = _make_service()

        with pytest.raises(ValueError, match="profile id"):
            service.list_users(profile_id="not-valid")

    # ------------------------------------------------------------------
    # list_permission_set_assignments
    # ------------------------------------------------------------------

    def test_list_permission_set_assignments_sends_query(self) -> None:
        """Query PermissionSetAssignment for a given user without extra filters."""
        payload = {
            "records": [
                {
                    "Id": _ASSIGNMENT_ID,
                    "AssigneeId": _USER_ID,
                    "PermissionSetId": _PERMISSION_SET_ID,
                }
            ]
        }
        service, transport = _make_service(content=_json_bytes(payload))

        result = service.list_permission_set_assignments(_USER_ID)

        sent = transport.send.call_args[0][0]
        assert sent.url.endswith("/services/data/v59.0/query")
        q = sent.params["q"]
        assert "FROM PermissionSetAssignment" in q
        assert f"AssigneeId = '{_USER_ID}'" in q
        assert result[0]["Id"] == _ASSIGNMENT_ID

    def test_list_permission_set_assignments_with_permission_set_id_filter(
        self,
    ) -> None:
        """Add PermissionSetId condition when permission_set_id is provided."""
        payload: dict[str, list[object]] = {"records": []}
        service, transport = _make_service(content=_json_bytes(payload))

        service.list_permission_set_assignments(
            _USER_ID, permission_set_id=_PERMISSION_SET_ID
        )

        sent = transport.send.call_args[0][0]
        q = sent.params["q"]
        assert f"PermissionSetId = '{_PERMISSION_SET_ID}'" in q

    def test_list_permission_set_assignments_raises_for_invalid_permission_set_id(
        self,
    ) -> None:
        """Raise ValueError when permission_set_id is malformed."""
        service, _ = _make_service()

        with pytest.raises(ValueError, match="permission set id"):
            service.list_permission_set_assignments(_USER_ID, permission_set_id="bad")

    # ------------------------------------------------------------------
    # revoke_permission_set
    # ------------------------------------------------------------------

    def test_revoke_permission_set_sends_delete(self) -> None:
        """Send DELETE to the PermissionSetAssignment SObject endpoint."""
        service, transport = _make_service(status_code=204, content=b"")

        service.revoke_permission_set(_ASSIGNMENT_ID)

        sent = transport.send.call_args[0][0]
        assert sent.method == "DELETE"
        assert sent.url.endswith(
            f"/services/data/v59.0/sobjects/PermissionSetAssignment/{_ASSIGNMENT_ID}"
        )

    def test_revoke_permission_set_raises_for_invalid_assignment_id(self) -> None:
        """Raise ValueError for a malformed assignment id."""
        service, _ = _make_service()

        with pytest.raises(ValueError, match="permission set assignment id"):
            service.revoke_permission_set("nope")

    # ------------------------------------------------------------------
    # list_permission_set_group_assignments
    # ------------------------------------------------------------------

    def test_list_permission_set_group_assignments_sends_query(self) -> None:
        """Query PermissionSetGroupAssignment for a given user."""
        payload = {
            "records": [
                {
                    "Id": _ASSIGNMENT_ID,
                    "AssigneeId": _USER_ID,
                    "PermissionSetGroupId": _PERMISSION_SET_GROUP_ID,
                }
            ]
        }
        service, transport = _make_service(content=_json_bytes(payload))

        result = service.list_permission_set_group_assignments(_USER_ID)

        sent = transport.send.call_args[0][0]
        q = sent.params["q"]
        assert "FROM PermissionSetGroupAssignment" in q
        assert f"AssigneeId = '{_USER_ID}'" in q
        assert result[0]["Id"] == _ASSIGNMENT_ID

    def test_list_permission_set_group_assignments_with_group_id_filter(self) -> None:
        """Add PermissionSetGroupId condition when permission_set_group_id is given."""
        payload: dict[str, list[object]] = {"records": []}
        service, transport = _make_service(content=_json_bytes(payload))

        service.list_permission_set_group_assignments(
            _USER_ID,
            permission_set_group_id=_PERMISSION_SET_GROUP_ID,
        )

        sent = transport.send.call_args[0][0]
        q = sent.params["q"]
        assert f"PermissionSetGroupId = '{_PERMISSION_SET_GROUP_ID}'" in q

    def test_list_permission_set_group_assignments_raises_for_invalid_group_id(
        self,
    ) -> None:
        """Raise ValueError when permission_set_group_id is malformed."""
        service, _ = _make_service()

        with pytest.raises(ValueError, match="permission set group id"):
            service.list_permission_set_group_assignments(
                _USER_ID, permission_set_group_id="x"
            )

    # ------------------------------------------------------------------
    # assign_permission_set_group (sync)
    # ------------------------------------------------------------------

    def test_assign_permission_set_group_posts_payload(self) -> None:
        """Create group assignment through the sobject endpoint."""
        payload = {"id": _ASSIGNMENT_ID, "success": True, "errors": []}
        service, transport = _make_service(
            status_code=201, content=_json_bytes(payload)
        )

        result = service.assign_permission_set_group(_USER_ID, _PERMISSION_SET_GROUP_ID)

        sent = transport.send.call_args[0][0]
        assert sent.method == "POST"
        assert sent.url.endswith(
            "/services/data/v59.0/sobjects/PermissionSetGroupAssignment"
        )
        body = json.loads(sent.content)
        assert body == {
            "AssigneeId": _USER_ID,
            "PermissionSetGroupId": _PERMISSION_SET_GROUP_ID,
        }
        assert result.id == _ASSIGNMENT_ID
        assert result.success is True

    # ------------------------------------------------------------------
    # set_user_active with True
    # ------------------------------------------------------------------

    def test_set_user_active_true_patches_with_true(self) -> None:
        """Patch User IsActive with True when activating."""
        service, transport = _make_service(status_code=204, content=b"")

        service.set_user_active(_USER_ID, True)

        sent = transport.send.call_args[0][0]
        assert sent.method == "PATCH"
        assert json.loads(sent.content) == {"IsActive": True}


class TestAsyncSalesforceIdentityAccessService:
    """Test suite for AsyncSalesforceIdentityAccessService."""

    @pytest.mark.asyncio
    async def test_query_records_returns_empty_for_non_dict_payload(self) -> None:
        """Return empty list when async query payload is not a JSON object."""
        service, _ = _make_async_service(content=b"[]")

        result = await service._query_records("SELECT Id FROM User")

        assert result == []

    @pytest.mark.asyncio
    async def test_query_records_returns_empty_when_records_is_not_list(self) -> None:
        """Return empty list when async payload contains non-list records."""
        service, _ = _make_async_service(content=_json_bytes({"records": "invalid"}))

        result = await service._query_records("SELECT Id FROM User")

        assert result == []

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

    # ------------------------------------------------------------------
    # get_user (async)
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_get_user_returns_user_dict(self) -> None:
        """Return user record dict from async SObject endpoint."""
        user_payload = {"Id": _USER_ID, "Username": "bob@example.com"}
        service, transport = _make_async_service(content=_json_bytes(user_payload))

        result = await service.get_user(_USER_ID)

        sent = transport.send.call_args[0][0]
        assert sent.method == "GET"
        assert sent.url.endswith(f"/services/data/v59.0/sobjects/User/{_USER_ID}")
        assert result["Id"] == _USER_ID

    @pytest.mark.asyncio
    async def test_get_user_raises_for_invalid_id(self) -> None:
        """Raise ValueError for a malformed user id in async service."""
        service, _ = _make_async_service()

        with pytest.raises(ValueError, match="user id"):
            await service.get_user("not-valid!")

    @pytest.mark.asyncio
    async def test_get_user_returns_empty_dict_for_non_dict_response(self) -> None:
        """Return empty dict when async response body is not a JSON object."""
        service, _ = _make_async_service(content=b"null")

        result = await service.get_user(_USER_ID)

        assert result == {}

    # ------------------------------------------------------------------
    # list_users (async)
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_list_users_with_filters(self) -> None:
        """Send filtered SOQL query on async service."""
        payload = {"records": [{"Id": _USER_ID, "Username": "bob@example.com"}]}
        service, transport = _make_async_service(content=_json_bytes(payload))

        result = await service.list_users(username="bob@example.com", is_active=False)

        sent = transport.send.call_args[0][0]
        q = sent.params["q"]
        assert "FROM User" in q
        assert "Username = 'bob@example.com'" in q
        assert "IsActive = false" in q
        assert result[0]["Id"] == _USER_ID

    @pytest.mark.asyncio
    async def test_list_users_raises_for_invalid_profile_id(self) -> None:
        """Raise ValueError when async list_users receives malformed profile_id."""
        service, _ = _make_async_service()

        with pytest.raises(ValueError, match="profile id"):
            await service.list_users(profile_id="bad-id")

    @pytest.mark.asyncio
    async def test_list_users_with_email_and_profile_filters(self) -> None:
        """Include Email and ProfileId predicates in async list_users SOQL."""
        payload: dict[str, list[object]] = {"records": []}
        service, transport = _make_async_service(content=_json_bytes(payload))

        await service.list_users(
            email="alice@example.com",
            profile_id=_PERMISSION_SET_ID,
        )

        sent = transport.send.call_args[0][0]
        q = sent.params["q"]
        assert "Email = 'alice@example.com'" in q
        assert f"ProfileId = '{_PERMISSION_SET_ID}'" in q

    # ------------------------------------------------------------------
    # list_permission_set_assignments (async)
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_list_permission_set_assignments_sends_query(self) -> None:
        """Query PermissionSetAssignment for a given user on async service."""
        payload = {
            "records": [
                {
                    "Id": _ASSIGNMENT_ID,
                    "AssigneeId": _USER_ID,
                    "PermissionSetId": _PERMISSION_SET_ID,
                }
            ]
        }
        service, transport = _make_async_service(content=_json_bytes(payload))

        result = await service.list_permission_set_assignments(_USER_ID)

        sent = transport.send.call_args[0][0]
        q = sent.params["q"]
        assert "FROM PermissionSetAssignment" in q
        assert f"AssigneeId = '{_USER_ID}'" in q
        assert result[0]["Id"] == _ASSIGNMENT_ID

    @pytest.mark.asyncio
    async def test_list_permission_set_assignments_with_filter(self) -> None:
        """Add PermissionSetId condition when permission_set_id is provided (async)."""
        payload: dict[str, list[object]] = {"records": []}
        service, transport = _make_async_service(content=_json_bytes(payload))

        await service.list_permission_set_assignments(
            _USER_ID, permission_set_id=_PERMISSION_SET_ID
        )

        sent = transport.send.call_args[0][0]
        q = sent.params["q"]
        assert f"PermissionSetId = '{_PERMISSION_SET_ID}'" in q

    @pytest.mark.asyncio
    async def test_list_permission_set_assignments_raises_for_invalid_user_id(
        self,
    ) -> None:
        """Raise ValueError for malformed user id on async service."""
        service, _ = _make_async_service()

        with pytest.raises(ValueError, match="user id"):
            await service.list_permission_set_assignments("not-a-salesforce-id")

    # ------------------------------------------------------------------
    # assign_permission_set (async)
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_assign_permission_set_posts_assignment_payload(self) -> None:
        """Create permission set assignment through async sobject endpoint."""
        payload = {"id": _ASSIGNMENT_ID, "success": True, "errors": []}
        service, transport = _make_async_service(
            status_code=201, content=_json_bytes(payload)
        )

        result = await service.assign_permission_set(_USER_ID, _PERMISSION_SET_ID)

        sent = transport.send.call_args[0][0]
        assert sent.method == "POST"
        assert sent.url.endswith(
            "/services/data/v59.0/sobjects/PermissionSetAssignment"
        )
        assert json.loads(sent.content) == {
            "AssigneeId": _USER_ID,
            "PermissionSetId": _PERMISSION_SET_ID,
        }
        assert result.id == _ASSIGNMENT_ID
        assert result.success is True

    # ------------------------------------------------------------------
    # revoke_permission_set (async)
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_revoke_permission_set_sends_delete(self) -> None:
        """Send DELETE to PermissionSetAssignment SObject endpoint (async)."""
        service, transport = _make_async_service(status_code=204, content=b"")

        await service.revoke_permission_set(_ASSIGNMENT_ID)

        sent = transport.send.call_args[0][0]
        assert sent.method == "DELETE"
        assert sent.url.endswith(
            f"/services/data/v59.0/sobjects/PermissionSetAssignment/{_ASSIGNMENT_ID}"
        )

    @pytest.mark.asyncio
    async def test_revoke_permission_set_raises_for_invalid_id(self) -> None:
        """Raise ValueError for malformed assignment id on async revoke."""
        service, _ = _make_async_service()

        with pytest.raises(ValueError, match="permission set assignment id"):
            await service.revoke_permission_set("nope")

    # ------------------------------------------------------------------
    # list_permission_set_group_assignments without filter (async)
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_list_permission_set_group_assignments_without_filter(self) -> None:
        """Query PermissionSetGroupAssignment for a user without group filter."""
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

        result = await service.list_permission_set_group_assignments(_USER_ID)

        sent = transport.send.call_args[0][0]
        q = sent.params["q"]
        assert "FROM PermissionSetGroupAssignment" in q
        assert f"AssigneeId = '{_USER_ID}'" in q
        assert f"PermissionSetGroupId = '{_PERMISSION_SET_GROUP_ID}'" not in q
        assert result[0]["Id"] == _ASSIGNMENT_ID

    # ------------------------------------------------------------------
    # revoke_permission_set_group (async)
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_revoke_permission_set_group_sends_delete(self) -> None:
        """Send DELETE to PermissionSetGroupAssignment SObject endpoint (async)."""
        service, transport = _make_async_service(status_code=204, content=b"")

        await service.revoke_permission_set_group(_ASSIGNMENT_ID)

        sent = transport.send.call_args[0][0]
        assert sent.method == "DELETE"
        assert sent.url.endswith(
            f"/services/data/v59.0/sobjects/PermissionSetGroupAssignment/{_ASSIGNMENT_ID}"
        )

    # ------------------------------------------------------------------
    # set_user_active (async)
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_set_user_active_patches_user(self) -> None:
        """Patch User IsActive via async service."""
        service, transport = _make_async_service(status_code=204, content=b"")

        await service.set_user_active(_USER_ID, False)

        sent = transport.send.call_args[0][0]
        assert sent.method == "PATCH"
        assert sent.url.endswith(f"/services/data/v59.0/sobjects/User/{_USER_ID}")
        assert json.loads(sent.content) == {"IsActive": False}


class TestValidateId:
    """Test _validate_id static method shared by both service classes."""

    def test_valid_15_char_id_passes(self) -> None:
        """Accept a valid 15-character alphanumeric Salesforce ID."""
        SalesforceIdentityAccessService._validate_id("005000000000001", label="user id")

    def test_valid_18_char_id_passes(self) -> None:
        """Accept a valid 18-character alphanumeric Salesforce ID."""
        SalesforceIdentityAccessService._validate_id(
            "005000000000001AAA", label="user id"
        )

    def test_invalid_id_raises_value_error(self) -> None:
        """Raise ValueError for an ID that is neither 15 nor 18 characters."""
        with pytest.raises(ValueError, match="user id"):
            SalesforceIdentityAccessService._validate_id("short", label="user id")

    def test_invalid_id_includes_value_in_message(self) -> None:
        """Error message contains the offending value."""
        bad_id = "toolongforthat123456789"
        with pytest.raises(ValueError, match=bad_id):
            SalesforceIdentityAccessService._validate_id(bad_id, label="user id")

    def test_invalid_id_with_special_chars_raises(self) -> None:
        """Reject IDs containing non-alphanumeric characters."""
        with pytest.raises(ValueError, match="permission set id"):
            SalesforceIdentityAccessService._validate_id(
                "005-000-000-001!!", label="permission set id"
            )

    def test_async_service_validate_id_valid(self) -> None:
        """AsyncSalesforceIdentityAccessService._validate_id accepts valid IDs."""
        AsyncSalesforceIdentityAccessService._validate_id(
            "005000000000001AAA", label="user id"
        )

    def test_async_service_validate_id_invalid(self) -> None:
        """AsyncSalesforceIdentityAccessService._validate_id rejects invalid IDs."""
        with pytest.raises(ValueError, match="user id"):
            AsyncSalesforceIdentityAccessService._validate_id("nope", label="user id")
