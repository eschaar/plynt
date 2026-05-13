"""Pricebook lookup services."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from plynth.connectors.salesforce.lookup.base import (
    AsyncSalesforceLookupService,
    SalesforceLookupService,
)

_PRICEBOOK_DEFAULT_FIELDS = [
    "Id",
    "Name",
    "IsStandard",
    "IsActive",
    "CurrencyIsoCode",
]


class SalesforcePricebookLookupService(SalesforceLookupService):
    """Sync lookup convenience for Salesforce Pricebook resolution."""

    def list(
        self,
        *,
        name: str | None = None,
        is_standard: bool | None = None,
        is_active: bool | None = None,
        currency_iso_code: str | None = None,
        fields: Sequence[str] | None = None,
    ) -> list[dict[str, Any]]:
        """List Pricebook rows with optional filters."""
        return self._query(
            object_name="Pricebook2",
            optional_filters={
                "Name": name,
                "IsStandard": is_standard,
                "IsActive": is_active,
                "CurrencyIsoCode": currency_iso_code,
            },
            fields=fields or _PRICEBOOK_DEFAULT_FIELDS,
            order_by="Name ASC",
        )

    def get_standard(
        self,
        *,
        is_active: bool | None = None,
        fields: Sequence[str] | None = None,
    ) -> dict[str, Any] | None:
        """Return the standard Pricebook row."""
        rows = self._query(
            object_name="Pricebook2",
            required_filters={"IsStandard": True},
            optional_filters={"IsActive": is_active},
            fields=fields or _PRICEBOOK_DEFAULT_FIELDS,
            order_by="Name ASC",
            limit=1,
        )
        return rows[0] if rows else None


class AsyncSalesforcePricebookLookupService(AsyncSalesforceLookupService):
    """Async lookup convenience for Salesforce Pricebook resolution."""

    async def list(
        self,
        *,
        name: str | None = None,
        is_standard: bool | None = None,
        is_active: bool | None = None,
        currency_iso_code: str | None = None,
        fields: Sequence[str] | None = None,
    ) -> list[dict[str, Any]]:
        """List Pricebook rows with optional filters."""
        return await self._query(
            object_name="Pricebook2",
            optional_filters={
                "Name": name,
                "IsStandard": is_standard,
                "IsActive": is_active,
                "CurrencyIsoCode": currency_iso_code,
            },
            fields=fields or _PRICEBOOK_DEFAULT_FIELDS,
            order_by="Name ASC",
        )

    async def get_standard(
        self,
        *,
        is_active: bool | None = None,
        fields: Sequence[str] | None = None,
    ) -> dict[str, Any] | None:
        """Return the standard Pricebook row."""
        rows = await self._query(
            object_name="Pricebook2",
            required_filters={"IsStandard": True},
            optional_filters={"IsActive": is_active},
            fields=fields or _PRICEBOOK_DEFAULT_FIELDS,
            order_by="Name ASC",
            limit=1,
        )
        return rows[0] if rows else None
