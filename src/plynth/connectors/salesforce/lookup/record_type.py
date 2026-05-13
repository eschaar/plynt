"""RecordType lookup services."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from plynth.connectors.salesforce.lookup.base import (
    AsyncSalesforceLookupService,
    SalesforceLookupService,
)

_RECORD_TYPE_DEFAULT_FIELDS = [
    "Id",
    "DeveloperName",
    "Name",
    "SobjectType",
    "IsActive",
]


class SalesforceRecordTypeLookupService(SalesforceLookupService):
    """Sync lookup convenience for Salesforce RecordType resolution."""

    def list(
        self,
        sobject_type: str,
        *,
        developer_name: str | None = None,
        name: str | None = None,
        is_active: bool | None = None,
        fields: Sequence[str] | None = None,
    ) -> list[dict[str, Any]]:
        """List RecordType rows for an SObject with optional filters."""
        return self._query(
            object_name="RecordType",
            required_filters={"SobjectType": sobject_type},
            optional_filters={
                "DeveloperName": developer_name,
                "Name": name,
                "IsActive": is_active,
            },
            fields=fields or _RECORD_TYPE_DEFAULT_FIELDS,
            order_by="DeveloperName ASC",
        )

    def get_by_developer_name(
        self,
        sobject_type: str,
        developer_name: str,
        *,
        fields: Sequence[str] | None = None,
    ) -> dict[str, Any] | None:
        """Return a single RecordType by SObject type and developer name."""
        rows = self._query(
            object_name="RecordType",
            required_filters={
                "SobjectType": sobject_type,
                "DeveloperName": developer_name,
            },
            fields=fields or _RECORD_TYPE_DEFAULT_FIELDS,
            order_by="DeveloperName ASC",
            limit=1,
        )
        return rows[0] if rows else None


class AsyncSalesforceRecordTypeLookupService(AsyncSalesforceLookupService):
    """Async lookup convenience for Salesforce RecordType resolution."""

    async def list(
        self,
        sobject_type: str,
        *,
        developer_name: str | None = None,
        name: str | None = None,
        is_active: bool | None = None,
        fields: Sequence[str] | None = None,
    ) -> list[dict[str, Any]]:
        """List RecordType rows for an SObject with optional filters."""
        return await self._query(
            object_name="RecordType",
            required_filters={"SobjectType": sobject_type},
            optional_filters={
                "DeveloperName": developer_name,
                "Name": name,
                "IsActive": is_active,
            },
            fields=fields or _RECORD_TYPE_DEFAULT_FIELDS,
            order_by="DeveloperName ASC",
        )

    async def get_by_developer_name(
        self,
        sobject_type: str,
        developer_name: str,
        *,
        fields: Sequence[str] | None = None,
    ) -> dict[str, Any] | None:
        """Return a single RecordType by SObject type and developer name."""
        rows = await self._query(
            object_name="RecordType",
            required_filters={
                "SobjectType": sobject_type,
                "DeveloperName": developer_name,
            },
            fields=fields or _RECORD_TYPE_DEFAULT_FIELDS,
            order_by="DeveloperName ASC",
            limit=1,
        )
        return rows[0] if rows else None
