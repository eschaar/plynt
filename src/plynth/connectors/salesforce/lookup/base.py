"""Base sync and async lookup service implementations."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Sequence
from typing import Any

from plynth.connectors.salesforce.constants import (
    resolve_async_api_version,
    resolve_sync_api_version,
)
from plynth.connectors.salesforce.helpers import build_select_soql, format_soql
from plynth.connectors.salesforce.models import SalesforceQueryResponse
from plynth.connectors.salesforce.renderer import SalesforceRenderer
from plynth.http.client import APIClient, AsyncAPIClient
from plynth.http.renderer import Renderer
from plynth.http.service import APIService, AsyncAPIService


class SalesforceLookupService(APIService):
    """Base sync lookup service for shared SOQL lookup mechanics."""

    def __init__(
        self,
        client: APIClient,
        *,
        api_version: str | None = None,
        renderer: Renderer | None = None,
    ) -> None:
        """Initialize SalesforceLookupService."""
        super().__init__(client, renderer=renderer or SalesforceRenderer())
        self._api_version = resolve_sync_api_version(client, api_version)

    def _query_path(self) -> str:
        """Return the Salesforce query endpoint path."""
        return f"/services/data/v{self._api_version}/query"

    def _query(
        self,
        *,
        object_name: str,
        required_filters: dict[str, Any] | None = None,
        optional_filters: dict[str, Any] | None = None,
        fields: Sequence[str],
        order_by: str,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """Execute a lookup SOQL query and return records."""
        where_parts: list[str] = []
        params: dict[str, Any] = {}

        for field_name, value in (required_filters or {}).items():
            param_name = field_name.lower()
            where_parts.append(f"{field_name} = :{param_name}")
            params[param_name] = value

        for field_name, value in (optional_filters or {}).items():
            if value is None:
                continue
            param_name = field_name.lower()
            where_parts.append(f"{field_name} = :{param_name}")
            params[param_name] = value

        query_template = build_select_soql(
            object_name,
            fields=fields,
            where=" AND ".join(where_parts) if where_parts else None,
            order_by=order_by,
            limit=limit,
        )
        soql = format_soql(query_template, **params)

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


class AsyncSalesforceLookupService(AsyncAPIService):
    """Base async lookup service for shared SOQL lookup mechanics."""

    def __init__(
        self,
        client: AsyncAPIClient,
        *,
        api_version: str | None = None,
        renderer: Renderer | None = None,
    ) -> None:
        """Initialize AsyncSalesforceLookupService."""
        super().__init__(client, renderer=renderer or SalesforceRenderer())
        self._api_version = api_version
        self._version_lock = asyncio.Lock()

    async def _ensure_api_version(self) -> str:
        """Resolve and cache the API version once per service instance."""
        if self._api_version is None:
            async with self._version_lock:
                if self._api_version is None:
                    self._api_version = await resolve_async_api_version(
                        self._client,
                        self._api_version,
                    )
        return self._api_version

    async def _query_path(self) -> str:
        """Return the Salesforce query endpoint path."""
        api_version = await self._ensure_api_version()
        return f"/services/data/v{api_version}/query"

    async def _query(
        self,
        *,
        object_name: str,
        required_filters: dict[str, Any] | None = None,
        optional_filters: dict[str, Any] | None = None,
        fields: Sequence[str],
        order_by: str,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """Execute a lookup SOQL query and return records."""
        where_parts: list[str] = []
        params: dict[str, Any] = {}

        for field_name, value in (required_filters or {}).items():
            param_name = field_name.lower()
            where_parts.append(f"{field_name} = :{param_name}")
            params[param_name] = value

        for field_name, value in (optional_filters or {}).items():
            if value is None:
                continue
            param_name = field_name.lower()
            where_parts.append(f"{field_name} = :{param_name}")
            params[param_name] = value

        query_template = build_select_soql(
            object_name,
            fields=fields,
            where=" AND ".join(where_parts) if where_parts else None,
            order_by=order_by,
            limit=limit,
        )
        soql = format_soql(query_template, **params)

        response = await self._client.get(
            await self._query_path(),
            params={"q": soql},
        )
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
