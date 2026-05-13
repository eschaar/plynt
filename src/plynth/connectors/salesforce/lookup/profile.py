"""Profile lookup services."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from plynth.connectors.salesforce.lookup.base import (
    AsyncSalesforceLookupService,
    SalesforceLookupService,
)

_PROFILE_DEFAULT_FIELDS = [
    "Id",
    "Name",
    "DeveloperName",
    "UserType",
]


class SalesforceProfileLookupService(SalesforceLookupService):
    """Sync lookup convenience for Salesforce Profile resolution."""

    def list(
        self,
        *,
        name: str | None = None,
        developer_name: str | None = None,
        user_type: str | None = None,
        fields: Sequence[str] | None = None,
    ) -> list[dict[str, Any]]:
        """List Profile rows with optional filters."""
        return self._query(
            object_name="Profile",
            optional_filters={
                "Name": name,
                "DeveloperName": developer_name,
                "UserType": user_type,
            },
            fields=fields or _PROFILE_DEFAULT_FIELDS,
            order_by="Name ASC",
        )

    def get_by_name(
        self,
        name: str,
        *,
        fields: Sequence[str] | None = None,
    ) -> dict[str, Any] | None:
        """Return a single Profile row by profile name."""
        rows = self._query(
            object_name="Profile",
            required_filters={"Name": name},
            fields=fields or _PROFILE_DEFAULT_FIELDS,
            order_by="Name ASC",
            limit=1,
        )
        return rows[0] if rows else None

    def get_by_developer_name(
        self,
        developer_name: str,
        *,
        fields: Sequence[str] | None = None,
    ) -> dict[str, Any] | None:
        """Return a single Profile row by profile developer name."""
        rows = self._query(
            object_name="Profile",
            required_filters={"DeveloperName": developer_name},
            fields=fields or _PROFILE_DEFAULT_FIELDS,
            order_by="DeveloperName ASC",
            limit=1,
        )
        return rows[0] if rows else None


class AsyncSalesforceProfileLookupService(AsyncSalesforceLookupService):
    """Async lookup convenience for Salesforce Profile resolution."""

    async def list(
        self,
        *,
        name: str | None = None,
        developer_name: str | None = None,
        user_type: str | None = None,
        fields: Sequence[str] | None = None,
    ) -> list[dict[str, Any]]:
        """List Profile rows with optional filters."""
        return await self._query(
            object_name="Profile",
            optional_filters={
                "Name": name,
                "DeveloperName": developer_name,
                "UserType": user_type,
            },
            fields=fields or _PROFILE_DEFAULT_FIELDS,
            order_by="Name ASC",
        )

    async def get_by_name(
        self,
        name: str,
        *,
        fields: Sequence[str] | None = None,
    ) -> dict[str, Any] | None:
        """Return a single Profile row by profile name."""
        rows = await self._query(
            object_name="Profile",
            required_filters={"Name": name},
            fields=fields or _PROFILE_DEFAULT_FIELDS,
            order_by="Name ASC",
            limit=1,
        )
        return rows[0] if rows else None

    async def get_by_developer_name(
        self,
        developer_name: str,
        *,
        fields: Sequence[str] | None = None,
    ) -> dict[str, Any] | None:
        """Return a single Profile row by profile developer name."""
        rows = await self._query(
            object_name="Profile",
            required_filters={"DeveloperName": developer_name},
            fields=fields or _PROFILE_DEFAULT_FIELDS,
            order_by="DeveloperName ASC",
            limit=1,
        )
        return rows[0] if rows else None
