"""Salesforce identity access primitives service.

Provides generic, policy-neutral wrappers for identity-related Salesforce
operations that are frequently needed across integrations.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

from plynth.connectors.salesforce.constants import (
    SALESFORCE_ID_RE,
    resolve_async_api_version,
    resolve_sync_api_version,
)
from plynth.connectors.salesforce.helpers import build_select_soql, format_soql
from plynth.connectors.salesforce.models import (
    SalesforceQueryResponse,
    SObjectCreateResult,
)
from plynth.connectors.salesforce.renderer import SalesforceRenderer
from plynth.http.client import APIClient, AsyncAPIClient
from plynth.http.renderer import Renderer
from plynth.http.service import APIService, AsyncAPIService

__all__ = [
    "AsyncSalesforceIdentityAccessService",
    "SalesforceIdentityAccessService",
]

_DEFAULT_USER_FIELDS = [
    "Id",
    "Username",
    "Name",
    "Email",
    "IsActive",
    "ProfileId",
]

_DEFAULT_PERMISSION_SET_ASSIGNMENT_FIELDS = [
    "Id",
    "AssigneeId",
    "PermissionSetId",
    "PermissionSet.Name",
    "PermissionSet.Label",
]

_DEFAULT_PERMISSION_SET_GROUP_ASSIGNMENT_FIELDS = [
    "Id",
    "AssigneeId",
    "PermissionSetGroupId",
    "PermissionSetGroup.DeveloperName",
    "PermissionSetGroup.MasterLabel",
]


class SalesforceIdentityAccessService(APIService):
    """Sync service for generic Salesforce identity access primitives."""

    def __init__(
        self,
        client: APIClient,
        *,
        api_version: str | None = None,
        renderer: Renderer | None = None,
    ) -> None:
        """Initialize SalesforceIdentityAccessService."""
        super().__init__(client, renderer=renderer or SalesforceRenderer())
        self._api_version = resolve_sync_api_version(client, api_version)

    @staticmethod
    def _validate_id(value: str, *, label: str) -> None:
        """Validate Salesforce 15/18-char record IDs used by identity helpers."""
        if not SALESFORCE_ID_RE.fullmatch(value):
            raise ValueError(f"Invalid Salesforce {label}: {value!r}")

    def _query_path(self) -> str:
        """Return the Salesforce query endpoint path."""
        return f"/services/data/v{self._api_version}/query"

    def _sobject_path(self, object_name: str, *parts: str) -> str:
        """Build a URL path under the SObject resource root."""
        base = f"/services/data/v{self._api_version}/sobjects/{object_name}"
        if parts:
            return f"{base}/{'/'.join(parts)}"
        return base

    def _query_records(self, soql: str) -> list[dict[str, Any]]:
        """Execute SOQL and return raw records list."""
        response = self._client.get(self._query_path(), params={"q": soql})
        payload = json.loads(response.content)
        if not isinstance(payload, dict):
            return []
        records = payload.get("records")
        if not isinstance(records, list):
            return []
        normalized_payload = {
            "totalSize": payload.get("totalSize", len(records)),
            "done": payload.get("done", True),
            "nextRecordsUrl": payload.get("nextRecordsUrl"),
            "records": records,
        }
        return SalesforceQueryResponse.model_validate(normalized_payload).records

    def get_user(
        self,
        user_id: str,
        *,
        fields: Sequence[str] | None = None,
    ) -> dict[str, Any]:
        """Return a Salesforce User by record ID."""
        self._validate_id(user_id, label="user id")
        params = {"fields": ",".join(fields)} if fields else None
        response = self._client.get(self._sobject_path("User", user_id), params=params)
        payload = json.loads(response.content)
        return payload if isinstance(payload, dict) else {}

    def list_users(
        self,
        *,
        username: str | None = None,
        email: str | None = None,
        is_active: bool | None = None,
        profile_id: str | None = None,
        fields: Sequence[str] | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """List User rows filtered by generic identity attributes."""
        if profile_id is not None:
            self._validate_id(profile_id, label="profile id")

        where_parts: list[str] = []
        params: dict[str, Any] = {}
        if username is not None:
            where_parts.append("Username = :username")
            params["username"] = username
        if email is not None:
            where_parts.append("Email = :email")
            params["email"] = email
        if is_active is not None:
            where_parts.append("IsActive = :is_active")
            params["is_active"] = is_active
        if profile_id is not None:
            where_parts.append("ProfileId = :profile_id")
            params["profile_id"] = profile_id

        template = build_select_soql(
            "User",
            fields=fields or _DEFAULT_USER_FIELDS,
            where=" AND ".join(where_parts) if where_parts else None,
            order_by="Username ASC",
            limit=limit,
        )
        return self._query_records(format_soql(template, **params))

    def list_permission_set_assignments(
        self,
        user_id: str,
        *,
        permission_set_id: str | None = None,
        fields: Sequence[str] | None = None,
    ) -> list[dict[str, Any]]:
        """List PermissionSetAssignment rows for a user."""
        self._validate_id(user_id, label="user id")
        if permission_set_id is not None:
            self._validate_id(permission_set_id, label="permission set id")

        where = "AssigneeId = :user_id"
        params: dict[str, Any] = {"user_id": user_id}
        if permission_set_id is not None:
            where += " AND PermissionSetId = :permission_set_id"
            params["permission_set_id"] = permission_set_id

        template = build_select_soql(
            "PermissionSetAssignment",
            fields=fields or _DEFAULT_PERMISSION_SET_ASSIGNMENT_FIELDS,
            where=where,
            order_by="PermissionSet.Name ASC",
        )
        return self._query_records(format_soql(template, **params))

    def assign_permission_set(
        self,
        user_id: str,
        permission_set_id: str,
    ) -> SObjectCreateResult:
        """Create a PermissionSetAssignment for a user."""
        self._validate_id(user_id, label="user id")
        self._validate_id(permission_set_id, label="permission set id")

        response = self._client.post(
            self._sobject_path("PermissionSetAssignment"),
            content=self._renderer.render(
                {
                    "AssigneeId": user_id,
                    "PermissionSetId": permission_set_id,
                }
            ),
        )
        return SObjectCreateResult.model_validate_json(response.content)

    def revoke_permission_set(self, assignment_id: str) -> None:
        """Delete an existing PermissionSetAssignment by assignment record ID."""
        self._validate_id(assignment_id, label="permission set assignment id")
        self._client.delete(
            self._sobject_path("PermissionSetAssignment", assignment_id)
        )

    def list_permission_set_group_assignments(
        self,
        user_id: str,
        *,
        permission_set_group_id: str | None = None,
        fields: Sequence[str] | None = None,
    ) -> list[dict[str, Any]]:
        """List PermissionSetGroupAssignment rows for a user."""
        self._validate_id(user_id, label="user id")
        if permission_set_group_id is not None:
            self._validate_id(permission_set_group_id, label="permission set group id")

        where = "AssigneeId = :user_id"
        params: dict[str, Any] = {"user_id": user_id}
        if permission_set_group_id is not None:
            where += " AND PermissionSetGroupId = :permission_set_group_id"
            params["permission_set_group_id"] = permission_set_group_id

        template = build_select_soql(
            "PermissionSetGroupAssignment",
            fields=fields or _DEFAULT_PERMISSION_SET_GROUP_ASSIGNMENT_FIELDS,
            where=where,
            order_by="PermissionSetGroup.DeveloperName ASC",
        )
        return self._query_records(format_soql(template, **params))

    def assign_permission_set_group(
        self,
        user_id: str,
        permission_set_group_id: str,
    ) -> SObjectCreateResult:
        """Create a PermissionSetGroupAssignment for a user."""
        self._validate_id(user_id, label="user id")
        self._validate_id(permission_set_group_id, label="permission set group id")

        response = self._client.post(
            self._sobject_path("PermissionSetGroupAssignment"),
            content=self._renderer.render(
                {
                    "AssigneeId": user_id,
                    "PermissionSetGroupId": permission_set_group_id,
                }
            ),
        )
        return SObjectCreateResult.model_validate_json(response.content)

    def revoke_permission_set_group(self, assignment_id: str) -> None:
        """Delete an existing PermissionSetGroupAssignment by assignment ID."""
        self._validate_id(assignment_id, label="permission set group assignment id")
        self._client.delete(
            self._sobject_path("PermissionSetGroupAssignment", assignment_id)
        )

    def set_user_active(self, user_id: str, is_active: bool) -> None:
        """Set the User IsActive flag without embedding business policy."""
        self._validate_id(user_id, label="user id")
        self._client.patch(
            self._sobject_path("User", user_id),
            content=self._renderer.render({"IsActive": is_active}),
        )


class AsyncSalesforceIdentityAccessService(AsyncAPIService):
    """Async service for generic Salesforce identity access primitives."""

    def __init__(
        self,
        client: AsyncAPIClient,
        *,
        api_version: str | None = None,
        renderer: Renderer | None = None,
    ) -> None:
        """Initialize AsyncSalesforceIdentityAccessService."""
        super().__init__(client, renderer=renderer or SalesforceRenderer())
        self._api_version = api_version

    @staticmethod
    def _validate_id(value: str, *, label: str) -> None:
        """Validate Salesforce 15/18-char record IDs used by identity helpers."""
        if not SALESFORCE_ID_RE.fullmatch(value):
            raise ValueError(f"Invalid Salesforce {label}: {value!r}")

    async def _query_path(self) -> str:
        """Return the Salesforce query endpoint path with lazy version resolution."""
        if self._api_version is None:
            self._api_version = await resolve_async_api_version(
                self._client,
                self._api_version,
            )
        return f"/services/data/v{self._api_version}/query"

    async def _sobject_path(self, object_name: str, *parts: str) -> str:
        """Build a URL path under the SObject resource root."""
        if self._api_version is None:
            self._api_version = await resolve_async_api_version(
                self._client,
                self._api_version,
            )
        base = f"/services/data/v{self._api_version}/sobjects/{object_name}"
        if parts:
            return f"{base}/{'/'.join(parts)}"
        return base

    async def _query_records(self, soql: str) -> list[dict[str, Any]]:
        """Execute SOQL and return raw records list."""
        response = await self._client.get(await self._query_path(), params={"q": soql})
        payload = json.loads(response.content)
        if not isinstance(payload, dict):
            return []
        records = payload.get("records")
        if not isinstance(records, list):
            return []
        normalized_payload = {
            "totalSize": payload.get("totalSize", len(records)),
            "done": payload.get("done", True),
            "nextRecordsUrl": payload.get("nextRecordsUrl"),
            "records": records,
        }
        return SalesforceQueryResponse.model_validate(normalized_payload).records

    async def get_user(
        self,
        user_id: str,
        *,
        fields: Sequence[str] | None = None,
    ) -> dict[str, Any]:
        """Return a Salesforce User by record ID."""
        self._validate_id(user_id, label="user id")
        params = {"fields": ",".join(fields)} if fields else None
        response = await self._client.get(
            await self._sobject_path("User", user_id), params=params
        )
        payload = json.loads(response.content)
        return payload if isinstance(payload, dict) else {}

    async def list_users(
        self,
        *,
        username: str | None = None,
        email: str | None = None,
        is_active: bool | None = None,
        profile_id: str | None = None,
        fields: Sequence[str] | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """List User rows filtered by generic identity attributes."""
        if profile_id is not None:
            self._validate_id(profile_id, label="profile id")

        where_parts: list[str] = []
        params: dict[str, Any] = {}
        if username is not None:
            where_parts.append("Username = :username")
            params["username"] = username
        if email is not None:
            where_parts.append("Email = :email")
            params["email"] = email
        if is_active is not None:
            where_parts.append("IsActive = :is_active")
            params["is_active"] = is_active
        if profile_id is not None:
            where_parts.append("ProfileId = :profile_id")
            params["profile_id"] = profile_id

        template = build_select_soql(
            "User",
            fields=fields or _DEFAULT_USER_FIELDS,
            where=" AND ".join(where_parts) if where_parts else None,
            order_by="Username ASC",
            limit=limit,
        )
        return await self._query_records(format_soql(template, **params))

    async def list_permission_set_assignments(
        self,
        user_id: str,
        *,
        permission_set_id: str | None = None,
        fields: Sequence[str] | None = None,
    ) -> list[dict[str, Any]]:
        """List PermissionSetAssignment rows for a user."""
        self._validate_id(user_id, label="user id")
        if permission_set_id is not None:
            self._validate_id(permission_set_id, label="permission set id")

        where = "AssigneeId = :user_id"
        params: dict[str, Any] = {"user_id": user_id}
        if permission_set_id is not None:
            where += " AND PermissionSetId = :permission_set_id"
            params["permission_set_id"] = permission_set_id

        template = build_select_soql(
            "PermissionSetAssignment",
            fields=fields or _DEFAULT_PERMISSION_SET_ASSIGNMENT_FIELDS,
            where=where,
            order_by="PermissionSet.Name ASC",
        )
        return await self._query_records(format_soql(template, **params))

    async def assign_permission_set(
        self,
        user_id: str,
        permission_set_id: str,
    ) -> SObjectCreateResult:
        """Create a PermissionSetAssignment for a user."""
        self._validate_id(user_id, label="user id")
        self._validate_id(permission_set_id, label="permission set id")

        response = await self._client.post(
            await self._sobject_path("PermissionSetAssignment"),
            content=self._renderer.render(
                {
                    "AssigneeId": user_id,
                    "PermissionSetId": permission_set_id,
                }
            ),
        )
        return SObjectCreateResult.model_validate_json(response.content)

    async def revoke_permission_set(self, assignment_id: str) -> None:
        """Delete an existing PermissionSetAssignment by assignment record ID."""
        self._validate_id(assignment_id, label="permission set assignment id")
        await self._client.delete(
            await self._sobject_path("PermissionSetAssignment", assignment_id)
        )

    async def list_permission_set_group_assignments(
        self,
        user_id: str,
        *,
        permission_set_group_id: str | None = None,
        fields: Sequence[str] | None = None,
    ) -> list[dict[str, Any]]:
        """List PermissionSetGroupAssignment rows for a user."""
        self._validate_id(user_id, label="user id")
        if permission_set_group_id is not None:
            self._validate_id(permission_set_group_id, label="permission set group id")

        where = "AssigneeId = :user_id"
        params: dict[str, Any] = {"user_id": user_id}
        if permission_set_group_id is not None:
            where += " AND PermissionSetGroupId = :permission_set_group_id"
            params["permission_set_group_id"] = permission_set_group_id

        template = build_select_soql(
            "PermissionSetGroupAssignment",
            fields=fields or _DEFAULT_PERMISSION_SET_GROUP_ASSIGNMENT_FIELDS,
            where=where,
            order_by="PermissionSetGroup.DeveloperName ASC",
        )
        return await self._query_records(format_soql(template, **params))

    async def assign_permission_set_group(
        self,
        user_id: str,
        permission_set_group_id: str,
    ) -> SObjectCreateResult:
        """Create a PermissionSetGroupAssignment for a user."""
        self._validate_id(user_id, label="user id")
        self._validate_id(permission_set_group_id, label="permission set group id")

        response = await self._client.post(
            await self._sobject_path("PermissionSetGroupAssignment"),
            content=self._renderer.render(
                {
                    "AssigneeId": user_id,
                    "PermissionSetGroupId": permission_set_group_id,
                }
            ),
        )
        return SObjectCreateResult.model_validate_json(response.content)

    async def revoke_permission_set_group(self, assignment_id: str) -> None:
        """Delete an existing PermissionSetGroupAssignment by assignment ID."""
        self._validate_id(assignment_id, label="permission set group assignment id")
        await self._client.delete(
            await self._sobject_path("PermissionSetGroupAssignment", assignment_id)
        )

    async def set_user_active(self, user_id: str, is_active: bool) -> None:
        """Set the User IsActive flag without embedding business policy."""
        self._validate_id(user_id, label="user id")
        await self._client.patch(
            await self._sobject_path("User", user_id),
            content=self._renderer.render({"IsActive": is_active}),
        )
