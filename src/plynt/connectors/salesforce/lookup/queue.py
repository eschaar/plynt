"""Queue lookup services."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from plynt.connectors.salesforce.lookup.base import (
    AsyncSalesforceLookupService,
    SalesforceLookupService,
)

_QUEUE_DEFAULT_FIELDS = [
    "Id",
    "Name",
    "DeveloperName",
    "Type",
]


class SalesforceQueueLookupService(SalesforceLookupService):
    """Sync lookup convenience for Salesforce Queue resolution."""

    def list(
        self,
        *,
        name: str | None = None,
        developer_name: str | None = None,
        fields: Sequence[str] | None = None,
    ) -> list[dict[str, Any]]:
        """List Queue rows with optional name and developer-name filters."""
        return self._query(
            object_name="Group",
            required_filters={"Type": "Queue"},
            optional_filters={
                "Name": name,
                "DeveloperName": developer_name,
            },
            fields=fields or _QUEUE_DEFAULT_FIELDS,
            order_by="Name ASC",
        )

    def get_by_name(
        self,
        name: str,
        *,
        fields: Sequence[str] | None = None,
    ) -> dict[str, Any] | None:
        """Return a single Queue row by queue name."""
        rows = self._query(
            object_name="Group",
            required_filters={"Type": "Queue", "Name": name},
            fields=fields or _QUEUE_DEFAULT_FIELDS,
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
        """Return a single Queue row by queue developer name."""
        rows = self._query(
            object_name="Group",
            required_filters={
                "Type": "Queue",
                "DeveloperName": developer_name,
            },
            fields=fields or _QUEUE_DEFAULT_FIELDS,
            order_by="DeveloperName ASC",
            limit=1,
        )
        return rows[0] if rows else None


class AsyncSalesforceQueueLookupService(AsyncSalesforceLookupService):
    """Async lookup convenience for Salesforce Queue resolution."""

    async def list(
        self,
        *,
        name: str | None = None,
        developer_name: str | None = None,
        fields: Sequence[str] | None = None,
    ) -> list[dict[str, Any]]:
        """List Queue rows with optional name and developer-name filters."""
        return await self._query(
            object_name="Group",
            required_filters={"Type": "Queue"},
            optional_filters={
                "Name": name,
                "DeveloperName": developer_name,
            },
            fields=fields or _QUEUE_DEFAULT_FIELDS,
            order_by="Name ASC",
        )

    async def get_by_name(
        self,
        name: str,
        *,
        fields: Sequence[str] | None = None,
    ) -> dict[str, Any] | None:
        """Return a single Queue row by queue name."""
        rows = await self._query(
            object_name="Group",
            required_filters={"Type": "Queue", "Name": name},
            fields=fields or _QUEUE_DEFAULT_FIELDS,
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
        """Return a single Queue row by queue developer name."""
        rows = await self._query(
            object_name="Group",
            required_filters={
                "Type": "Queue",
                "DeveloperName": developer_name,
            },
            fields=fields or _QUEUE_DEFAULT_FIELDS,
            order_by="DeveloperName ASC",
            limit=1,
        )
        return rows[0] if rows else None
