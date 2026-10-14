"""User lookup services."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from plynt.connectors.salesforce.lookup.base import (
    AsyncSalesforceLookupService,
    SalesforceLookupService,
)

_USER_DEFAULT_FIELDS = [
    "Id",
    "Username",
    "Email",
    "Alias",
    "FederationIdentifier",
    "IsActive",
]


class SalesforceUserLookupService(SalesforceLookupService):
    """Sync lookup convenience for Salesforce User resolution."""

    def list(
        self,
        *,
        username: str | None = None,
        email: str | None = None,
        alias: str | None = None,
        federation_id: str | None = None,
        is_active: bool | None = None,
        fields: Sequence[str] | None = None,
    ) -> list[dict[str, Any]]:
        """List User rows with optional identity and activity filters."""
        return self._query(
            object_name="User",
            optional_filters={
                "Username": username,
                "Email": email,
                "Alias": alias,
                "FederationIdentifier": federation_id,
                "IsActive": is_active,
            },
            fields=fields or _USER_DEFAULT_FIELDS,
            order_by="Username ASC",
        )

    def get_by_username(
        self,
        username: str,
        *,
        fields: Sequence[str] | None = None,
    ) -> dict[str, Any] | None:
        """Return a single User by username."""
        rows = self._query(
            object_name="User",
            required_filters={"Username": username},
            fields=fields or _USER_DEFAULT_FIELDS,
            order_by="Username ASC",
            limit=1,
        )
        return rows[0] if rows else None


class AsyncSalesforceUserLookupService(AsyncSalesforceLookupService):
    """Async lookup convenience for Salesforce User resolution."""

    async def list(
        self,
        *,
        username: str | None = None,
        email: str | None = None,
        alias: str | None = None,
        federation_id: str | None = None,
        is_active: bool | None = None,
        fields: Sequence[str] | None = None,
    ) -> list[dict[str, Any]]:
        """List User rows with optional identity and activity filters."""
        return await self._query(
            object_name="User",
            optional_filters={
                "Username": username,
                "Email": email,
                "Alias": alias,
                "FederationIdentifier": federation_id,
                "IsActive": is_active,
            },
            fields=fields or _USER_DEFAULT_FIELDS,
            order_by="Username ASC",
        )

    async def get_by_username(
        self,
        username: str,
        *,
        fields: Sequence[str] | None = None,
    ) -> dict[str, Any] | None:
        """Return a single User by username."""
        rows = await self._query(
            object_name="User",
            required_filters={"Username": username},
            fields=fields or _USER_DEFAULT_FIELDS,
            order_by="Username ASC",
            limit=1,
        )
        return rows[0] if rows else None
